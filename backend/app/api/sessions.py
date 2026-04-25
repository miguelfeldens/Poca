from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.session import Session
from app.schemas.session import SessionOut, SessionEndRequest

router = APIRouter(prefix="/sessions", tags=["sessions"])

# Gemini Live pricing (per minute)
AUDIO_INPUT_COST_PER_MIN = 0.005
AUDIO_OUTPUT_COST_PER_MIN = 0.018


@router.post("/start", response_model=SessionOut)
async def start_session(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    session = Session(
        user_id=uuid.UUID(user_id),
        session_start=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.patch("/{session_id}/end", response_model=SessionOut)
async def end_session(
    session_id: str,
    body: SessionEndRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(
            and_(Session.id == session_id, Session.user_id == user_id)
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.now(timezone.utc)
    session.session_end = now
    session.input_tokens = body.input_tokens
    session.output_tokens = body.output_tokens

    if session.session_start:
        delta = now - session.session_start
        session.duration_seconds = int(delta.total_seconds())
        # Rough cost estimate based on duration split 40/60 input/output
        duration_min = session.duration_seconds / 60
        session.estimated_cost_usd = round(
            (duration_min * 0.4 * AUDIO_INPUT_COST_PER_MIN) +
            (duration_min * 0.6 * AUDIO_OUTPUT_COST_PER_MIN),
            6
        )

    await db.flush()
    await db.refresh(session)
    return session


@router.get("/check-first-of-week")
async def check_first_session_of_week(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Returns whether this is the user's first session of the current week."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(Session).where(
            and_(
                Session.user_id == user_id,
                Session.session_start >= week_start,
            )
        ).limit(1)
    )
    existing = result.scalar_one_or_none()
    return {"is_first_of_week": existing is None}
