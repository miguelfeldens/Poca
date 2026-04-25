from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone, timedelta
from app.models.task import Task


async def get_weekly_accomplishments(db: AsyncSession, user_id: str) -> list[str]:
    """Get list of completed task titles from the current week."""
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.is_completed == True,
                Task.updated_at >= week_start,
            )
        ).order_by(Task.updated_at.desc())
    )
    tasks = result.scalars().all()
    return [t.title for t in tasks]
