from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class ContextItem(Base):
    __tablename__ = "context_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_type = Column(String, nullable=False)  # 'pdf', 'google_doc', 'google_sheet', 'url', 'web_search'
    title = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    content_text = Column(Text, nullable=True)
    auto_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
