from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class ContextItemCreate(BaseModel):
    item_type: str  # 'google_doc', 'google_sheet', 'url'
    title: str
    source_url: str


class ContextItemOut(BaseModel):
    id: uuid.UUID
    item_type: str
    title: str
    source_url: Optional[str] = None
    auto_expires_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
