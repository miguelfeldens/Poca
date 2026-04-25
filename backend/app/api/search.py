from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import uuid

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.context_item import ContextItem

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    save_to_context: bool = True


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    context_item_id: str | None = None


@router.post("/web", response_model=SearchResponse)
async def web_search(
    body: SearchRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Perform a web search and optionally save results to user context."""
    results = await _perform_search(body.query)

    context_item_id = None
    if body.save_to_context and results:
        # Compile results into a text block
        content_parts = [f"Web search results for: {body.query}\n"]
        for r in results[:5]:
            content_parts.append(f"## {r.title}\n{r.url}\n{r.snippet}\n")
        content_text = "\n".join(content_parts)

        item = ContextItem(
            user_id=uuid.UUID(user_id),
            item_type="web_search",
            title=f"Search: {body.query[:80]}",
            content_text=content_text,
            auto_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            last_synced_at=datetime.now(timezone.utc),
        )
        db.add(item)
        await db.flush()
        context_item_id = str(item.id)

    return SearchResponse(results=results, context_item_id=context_item_id)


async def _perform_search(query: str) -> list[SearchResult]:
    """
    Perform web search using DuckDuckGo (no API key required).
    For production, swap with Google Custom Search or Bing Search API.
    """
    import httpx
    from bs4 import BeautifulSoup

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "POCA/1.0 (+https://poca.app)"},
            )

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for result in soup.select(".result")[:8]:
            title_el = result.select_one(".result__title")
            url_el = result.select_one(".result__url")
            snippet_el = result.select_one(".result__snippet")

            if title_el and url_el:
                results.append(SearchResult(
                    title=title_el.get_text(strip=True),
                    url=url_el.get_text(strip=True),
                    snippet=snippet_el.get_text(strip=True) if snippet_el else "",
                ))

        return results
    except Exception:
        return []
