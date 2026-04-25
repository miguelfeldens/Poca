from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    task_type: str  # 'deadline', 'action_item', 'priority'
    due_date: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    is_completed: Optional[bool] = None
    calendar_event_id: Optional[str] = None


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    task_type: str
    due_date: Optional[datetime] = None
    is_completed: bool
    calendar_event_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
