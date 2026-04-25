from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import uuid


class RegisterRequest(BaseModel):
    passphrase: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    avatar_url: Optional[str] = None
    voice_preference: str
    dashboard_window_days: int
    voice_output_enabled: bool
    celebration_sounds: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
