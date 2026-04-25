from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate, TaskOut

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=List[TaskOut])
async def list_tasks(
    task_type: Optional[str] = None,
    include_completed: bool = False,
    days_ahead: int = 7,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conditions = [Task.user_id == user_id]
    if not include_completed:
        conditions.append(Task.is_completed == False)
    if task_type:
        conditions.append(Task.task_type == task_type)

    result = await db.execute(
        select(Task).where(and_(*conditions)).order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
    )
    return result.scalars().all()


@router.get("/overdue", response_model=List[TaskOut])
async def list_overdue_tasks(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.is_completed == False,
                Task.due_date < now,
                Task.task_type == "deadline",
            )
        ).order_by(Task.due_date.asc())
    )
    return result.scalars().all()


@router.get("/today", response_model=List[TaskOut])
async def list_todays_tasks(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    result = await db.execute(
        select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.is_completed == False,
                Task.due_date >= today_start,
                Task.due_date < today_end,
            )
        ).order_by(Task.due_date.asc())
    )
    return result.scalars().all()


@router.get("/accomplishments", response_model=List[TaskOut])
async def list_accomplishments(
    week: str = "current",
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
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
    return result.scalars().all()


@router.post("/", response_model=TaskOut)
async def create_task(
    task_in: TaskCreate,
    session_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    task = Task(
        user_id=uuid.UUID(user_id),
        session_id=uuid.UUID(session_id) if session_id else None,
        title=task_in.title,
        description=task_in.description,
        task_type=task_in.task_type,
        due_date=task_in.due_date,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    task_in: TaskUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in task_in.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    await db.flush()
    await db.refresh(task)
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(and_(Task.id == task_id, Task.user_id == user_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    return {"deleted": True}
