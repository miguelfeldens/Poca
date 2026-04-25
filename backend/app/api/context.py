from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid
import os

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.context_item import ContextItem
from app.schemas.context import ContextItemCreate, ContextItemOut

router = APIRouter(prefix="/context", tags=["context"])

UPLOAD_DIR = "/tmp/poca_uploads"


@router.get("/", response_model=List[ContextItemOut])
async def list_context_items(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Auto-expire web search results
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(ContextItem).where(
            and_(
                ContextItem.user_id == user_id,
                (ContextItem.auto_expires_at == None) | (ContextItem.auto_expires_at > now),
            )
        ).order_by(ContextItem.created_at.desc())
    )
    return result.scalars().all()


@router.post("/upload", response_model=ContextItemOut)
async def upload_pdf(
    file: UploadFile = File(...),
    title: str = Form(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{uuid.uuid4()}_{file.filename}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text from PDF
    text = ""
    try:
        import PyPDF2
        import io
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        text = "(PDF text extraction failed)"

    item = ContextItem(
        user_id=uuid.UUID(user_id),
        item_type="pdf",
        title=title,
        file_path=file_path,
        content_text=text[:50000],  # Cap at 50k chars
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.post("/link", response_model=ContextItemOut)
async def add_linked_context(
    item_in: ContextItemCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    text = await _fetch_url_content(item_in.source_url, item_in.item_type)

    expires_at = None
    if item_in.item_type == "web_search":
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    item = ContextItem(
        user_id=uuid.UUID(user_id),
        item_type=item_in.item_type,
        title=item_in.title,
        source_url=item_in.source_url,
        content_text=text[:50000] if text else None,
        auto_expires_at=expires_at,
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.post("/{item_id}/resync", response_model=ContextItemOut)
async def resync_context_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ContextItem).where(
            and_(ContextItem.id == item_id, ContextItem.user_id == user_id)
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Context item not found")
    if not item.source_url:
        raise HTTPException(status_code=400, detail="No URL to resync")

    text = await _fetch_url_content(item.source_url, item.item_type)
    if text:
        item.content_text = text[:50000]
    item.last_synced_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/{item_id}")
async def delete_context_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ContextItem).where(
            and_(ContextItem.id == item_id, ContextItem.user_id == user_id)
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Context item not found")

    # Clean up file if exists
    if item.file_path and os.path.exists(item.file_path):
        os.remove(item.file_path)

    await db.delete(item)
    return {"deleted": True}


async def _fetch_url_content(url: str, item_type: str) -> Optional[str]:
    """Fetch and extract text content from a URL."""
    import httpx
    from bs4 import BeautifulSoup

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()

        if item_type in ("google_doc", "google_sheet"):
            # Google Docs export as plain text
            if "docs.google.com" in url:
                export_url = url.replace("/edit", "/export?format=txt")
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(export_url, follow_redirects=True)
                return resp.text

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        return None
