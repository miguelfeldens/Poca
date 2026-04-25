from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.user import User

router = APIRouter(prefix="/calendar", tags=["calendar"])


class CalendarEventCreate(BaseModel):
    title: str
    start: datetime
    end: Optional[datetime] = None
    description: Optional[str] = None


class CalendarEventOut(BaseModel):
    id: str
    title: str
    start: datetime
    end: Optional[datetime] = None
    description: Optional[str] = None
    all_day: bool = False


async def get_calendar_service(user: User):
    """Build Google Calendar API service for the user."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from app.core.config import get_settings

    settings = get_settings()

    if not user.google_access_token:
        raise HTTPException(status_code=403, detail="Google Calendar not connected")

    creds = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    return build("calendar", "v3", credentials=creds)


@router.get("/events", response_model=List[CalendarEventOut])
async def list_calendar_events(
    days_ahead: int = 30,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    service = await get_calendar_service(user)

    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_ahead)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        maxResults=100,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = []
    for item in events_result.get("items", []):
        start = item["start"].get("dateTime", item["start"].get("date"))
        end = item["end"].get("dateTime", item["end"].get("date"))
        all_day = "date" in item["start"]

        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end) if end else None
        except ValueError:
            continue

        events.append(CalendarEventOut(
            id=item["id"],
            title=item.get("summary", "Untitled"),
            start=start_dt,
            end=end_dt,
            description=item.get("description"),
            all_day=all_day,
        ))

    return events


@router.post("/events", response_model=CalendarEventOut)
async def create_calendar_event(
    event_in: CalendarEventCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    service = await get_calendar_service(user)

    end_time = event_in.end or (event_in.start + timedelta(hours=1))

    event_body = {
        "summary": event_in.title,
        "description": event_in.description or "",
        "start": {"dateTime": event_in.start.isoformat()},
        "end": {"dateTime": end_time.isoformat()},
    }

    created = service.events().insert(calendarId="primary", body=event_body).execute()

    return CalendarEventOut(
        id=created["id"],
        title=created.get("summary", ""),
        start=event_in.start,
        end=end_time,
        description=event_in.description,
    )
