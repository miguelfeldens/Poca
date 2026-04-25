from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class SessionOut(BaseModel):
    id: uuid.UUID
    session_start: datetime
    session_end: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    model_used: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Optional[float] = None

    class Config:
        from_attributes = True


class SessionEndRequest(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
