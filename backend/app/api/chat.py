"""
Gemini Live API WebSocket proxy.

Protocol:
  Client → Server:
    {"type": "audio", "data": "<base64-pcm16>"}
    {"type": "text", "data": "message text"}
    {"type": "end_turn"}

  Server → Client:
    {"type": "text", "data": "...", "role": "assistant"}
    {"type": "audio", "data": "<base64-pcm16>"}
    {"type": "dashboard_update", "tasks": [...]}
    {"type": "calendar_confirm", "event": {...}}
    {"type": "search_confirm", "query": "..."}
    {"type": "error", "message": "..."}
    {"type": "session_started", "session_id": "..."}
"""
import asyncio
import base64
import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

import google.generativeai as genai

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.gemini import POCA_SYSTEM_PROMPT, build_session_context, synthesize_speech
from app.core.security import decode_token
from app.models.session import Session
from app.models.task import Task
from app.models.context_item import ContextItem
from app.models.user import User
from app.services.memory import store_message, retrieve_relevant_context
from app.services.accomplishments import get_weekly_accomplishments

router = APIRouter(tags=["chat"])
settings = get_settings()


def _build_google_credentials(user: "User"):
    """Build Google OAuth credentials from stored user tokens."""
    from google.oauth2.credentials import Credentials
    return Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def _fetch_calendar_events_sync(user: "User") -> list:
    """Fetch upcoming calendar events (next 30 days) synchronously."""
    try:
        from googleapiclient.discovery import build
        from datetime import datetime, timezone, timedelta

        creds = _build_google_credentials(user)
        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=30)
        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=30,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = []
        for item in result.get("items", []):
            start = item["start"].get("dateTime", item["start"].get("date", ""))
            events.append({"title": item.get("summary", "Untitled"), "start": start})
        return events
    except Exception as e:
        print(f"[Calendar] Error fetching events: {e}")
        return []


def _fetch_recent_emails_sync(user: "User", days: int = 14, max_results: int = 10) -> list:
    """Fetch emails from the last N days for session context."""
    try:
        from googleapiclient.discovery import build

        creds = _build_google_credentials(user)
        service = build("gmail", "v1", credentials=creds)
        resp = service.users().messages().list(
            userId="me",
            q=f"newer_than:{days}d",
            maxResults=max_results,
        ).execute()
        messages = resp.get("messages", [])
        emails = []
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            snippet = detail.get("snippet", "")[:150]
            emails.append({
                "subject": headers.get("Subject", "N/A"),
                "from": headers.get("From", "N/A"),
                "date": headers.get("Date", "N/A"),
                "snippet": snippet,
            })
        return emails
    except Exception as e:
        print(f"[Gmail] Error fetching recent emails: {e}")
        return []


def _fetch_gmail_results_sync(user: "User", query: str) -> str:
    """Search Gmail and return formatted results."""
    try:
        from googleapiclient.discovery import build

        creds = _build_google_credentials(user)
        service = build("gmail", "v1", credentials=creds)
        resp = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
        messages = resp.get("messages", [])
        if not messages:
            return "No emails found."
        lines = []
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            snippet = detail.get("snippet", "")
            lines.append(
                f"- Subject: {headers.get('Subject', 'N/A')} | From: {headers.get('From', 'N/A')} | Date: {headers.get('Date', 'N/A')}\n"
                f"  Preview: {snippet[:200]}"
            )
        return "\n".join(lines)
    except Exception as e:
        print(f"[Gmail] Error: {e}")
        return f"Could not search Gmail: {e}"


def _fetch_drive_results_sync(user: "User", query: str) -> str:
    """Search Google Drive and return formatted results."""
    try:
        from googleapiclient.discovery import build

        creds = _build_google_credentials(user)
        service = build("drive", "v3", credentials=creds)
        escaped = query.replace("'", "\\'")
        resp = service.files().list(
            q=f"fullText contains '{escaped}'",
            pageSize=5,
            fields="files(name,mimeType,modifiedTime,webViewLink)",
            orderBy="modifiedTime desc",
        ).execute()
        files = resp.get("files", [])
        if not files:
            return "No files found."
        lines = []
        for f in files:
            lines.append(
                f"- {f['name']} ({f.get('mimeType','').split('.')[-1]}) — modified {f.get('modifiedTime','N/A')[:10]}\n"
                f"  Link: {f.get('webViewLink', 'N/A')}"
            )
        return "\n".join(lines)
    except Exception as e:
        print(f"[Drive] Error: {e}")
        return f"Could not search Drive: {e}"


async def _get_session_opening_context(db: AsyncSession, user_id: str, local_datetime: str = None, user: "User" = None) -> str:
    """Build context for session opening sequence."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # Overdue tasks
    overdue_result = await db.execute(
        select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.is_completed == False,
                Task.due_date < today_start,
                Task.task_type == "deadline",
            )
        ).order_by(Task.due_date.asc()).limit(10)
    )
    overdue_tasks = [
        {"title": t.title, "due_date": t.due_date.strftime("%B %d") if t.due_date else "unknown"}
        for t in overdue_result.scalars().all()
    ]

    # Today's tasks
    today_result = await db.execute(
        select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.is_completed == False,
                Task.due_date >= today_start,
                Task.due_date < today_end,
            )
        ).order_by(Task.due_date.asc()).limit(10)
    )
    todays_tasks = [{"title": t.title} for t in today_result.scalars().all()]

    # Context documents (non-expired)
    ctx_result = await db.execute(
        select(ContextItem).where(
            and_(
                ContextItem.user_id == user_id,
                (ContextItem.auto_expires_at == None) | (ContextItem.auto_expires_at > now),
            )
        ).limit(20)
    )
    context_docs = [
        {"title": c.title, "content_text": c.content_text}
        for c in ctx_result.scalars().all()
    ]

    # Check if first session of week
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    session_result = await db.execute(
        select(Session).where(
            and_(Session.user_id == user_id, Session.session_start >= week_start)
        ).limit(1)
    )
    is_first_of_week = session_result.scalar_one_or_none() is None

    weekly_accomplishments = []
    if is_first_of_week:
        weekly_accomplishments = await get_weekly_accomplishments(db, user_id)

    # Retrieve relevant memory snippets (use generic session-start query)
    memory_snippets = await retrieve_relevant_context(
        db, user_id, "what are the user's current projects and priorities", top_k=8
    )

    current_dt = local_datetime if local_datetime else now.strftime("%A, %B %d, %Y — %I:%M %p UTC")

    # Fetch Google data if user has tokens — 8s timeout each so slow APIs never block startup
    upcoming_events = []
    recent_emails = []
    if user and user.google_access_token:
        results = await asyncio.gather(
            asyncio.wait_for(asyncio.to_thread(_fetch_calendar_events_sync, user), timeout=8),
            asyncio.wait_for(asyncio.to_thread(_fetch_recent_emails_sync, user), timeout=8),
            return_exceptions=True,
        )
        upcoming_events = results[0] if isinstance(results[0], list) else []
        recent_emails = results[1] if isinstance(results[1], list) else []

    return build_session_context(
        overdue_tasks=overdue_tasks,
        todays_tasks=todays_tasks,
        context_docs=context_docs,
        memory_snippets=memory_snippets,
        is_first_session_of_week=is_first_of_week,
        weekly_accomplishments=weekly_accomplishments,
        current_datetime=current_dt,
        upcoming_events=upcoming_events,
        recent_emails=recent_emails,
    )


def _split_into_chunks(text: str) -> list[str]:
    """Split text into sentence-sized chunks for faster chunked TTS."""
    # Split on sentence-ending punctuation followed by whitespace
    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    buf = ""
    for s in raw:
        if not s:
            continue
        buf = (buf + " " + s).strip() if buf else s
        # Emit chunk when it's long enough (avoids tiny TTS calls)
        if len(buf) >= 60:
            chunks.append(buf)
            buf = ""
    if buf:
        if chunks:
            chunks[-1] += " " + buf
        else:
            chunks.append(buf)
    return chunks or [text]


def _parse_poca_directives(text: str) -> dict:
    """Extract <extract>, <complete>, <calendar_add>, <web_search> tags from POCA response."""
    result = {
        "clean_text": text,
        "extractions": [],
        "completions": [],
        "calendar_adds": [],
        "web_searches": [],
        "gmail_searches": [],
        "drive_searches": [],
    }

    # Remove and parse each directive tag
    for tag, key in [
        ("extract", "extractions"),
        ("complete", "completions"),
        ("calendar_add", "calendar_adds"),
        ("web_search", "web_searches"),
        ("gmail_search", "gmail_searches"),
        ("drive_search", "drive_searches"),
    ]:
        pattern = rf"<{tag}>(.*?)</{tag}>"
        matches = re.findall(pattern, text, re.DOTALL)
        for m in matches:
            try:
                result[key].append(json.loads(m.strip()))
            except json.JSONDecodeError:
                pass
        # Remove tags from display text
        result["clean_text"] = re.sub(pattern, "", result["clean_text"], flags=re.DOTALL).strip()

    return result


async def _save_extracted_tasks(db: AsyncSession, user_id: str, session_id: str, extractions: list) -> list:
    """Save extracted tasks from POCA response to DB."""
    saved = []
    for item in extractions:
        task_type = item.get("type", "action_item")
        if task_type not in ("deadline", "action_item", "priority"):
            task_type = "action_item"

        due_date = None
        if item.get("due_date"):
            try:
                due_date = datetime.fromisoformat(item["due_date"])
            except ValueError:
                pass

        task = Task(
            user_id=uuid.UUID(user_id),
            session_id=uuid.UUID(session_id),
            title=item.get("title", "Untitled task"),
            description=item.get("description"),
            task_type=task_type,
            due_date=due_date,
        )
        db.add(task)
        await db.flush()
        await db.refresh(task)
        saved.append({
            "id": str(task.id),
            "title": task.title,
            "task_type": task.task_type,
            "due_date": task.due_date.isoformat() if task.due_date else None,
        })
    return saved


async def _complete_tasks_by_title(db: AsyncSession, user_id: str, completions: list):
    """Mark tasks as completed based on title match."""
    for item in completions:
        title = item.get("task_title", "")
        result = await db.execute(
            select(Task).where(
                and_(
                    Task.user_id == user_id,
                    Task.title.ilike(f"%{title}%"),
                    Task.is_completed == False,
                )
            ).limit(1)
        )
        task = result.scalar_one_or_none()
        if task:
            task.is_completed = True


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    local_datetime: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time chat with POCA via Gemini.
    Accepts both text and audio (base64 PCM16) messages.
    """
    # Authenticate
    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    async with AsyncSessionLocal() as db:
        try:
            # Verify session belongs to user
            result = await db.execute(
                select(Session).where(
                    and_(Session.id == session_id, Session.user_id == user_id)
                )
            )
            session = result.scalar_one_or_none()
            if not session:
                await websocket.send_json({"type": "error", "message": "Session not found"})
                await websocket.close()
                return

            # Fetch user for Google API access
            user_result = await db.execute(select(User).where(User.id == user_id))
            current_user = user_result.scalar_one_or_none()

            # Build opening context
            opening_context = await _get_session_opening_context(db, user_id, local_datetime, user=current_user)
            full_system_prompt = POCA_SYSTEM_PROMPT
            if opening_context:
                full_system_prompt += f"\n\n## Current Session Context\n{opening_context}"

            await websocket.send_json({"type": "session_started", "session_id": session_id})

            # Initialize Gemini model for text chat
            # Note: For production Gemini Live audio, use the Live API client separately
            model = genai.GenerativeModel(
                model_name=get_settings().gemini_model,
                system_instruction=full_system_prompt,
            )
            chat = model.start_chat(history=[])

            voice = (current_user.voice_preference if current_user and current_user.voice_preference else "Aoede")

            async def send_poca_response(text: str):
                """Send text immediately, then stream TTS audio sentence by sentence."""
                await websocket.send_json({"type": "text", "data": text, "role": "assistant"})
                chunks = _split_into_chunks(text)
                for i, chunk in enumerate(chunks):
                    tts = await synthesize_speech(chunk, voice=voice)
                    if tts:
                        audio_bytes, mime_type = tts
                        await websocket.send_json({
                            "type": "audio_response",
                            "data": base64.b64encode(audio_bytes).decode(),
                            "mime_type": mime_type,
                        })

            # Send opening message from POCA
            opening_msg = await asyncio.to_thread(
                lambda: chat.send_message(
                    "Begin the session. Follow the opening sequence: "
                    "housekeeping (overdue items), today's priorities, then open invitation. "
                    "Keep it concise — this is spoken aloud."
                )
            )
            opening_text = opening_msg.text
            parsed = _parse_poca_directives(opening_text)

            await send_poca_response(parsed["clean_text"])
            await store_message(db, session_id, user_id, "assistant", parsed["clean_text"])
            await db.commit()

            # Main message loop
            while True:
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=300)
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "error", "message": "Session timeout"})
                    break

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type == "text":
                    user_text = msg.get("data", "").strip()
                    if not user_text:
                        continue

                    await store_message(db, session_id, user_id, "user", user_text)

                    # Get Gemini response
                    response = await asyncio.to_thread(
                        lambda: chat.send_message(user_text)
                    )
                    response_text = response.text
                    parsed = _parse_poca_directives(response_text)

                    # Send text + audio to client
                    await send_poca_response(parsed["clean_text"])

                    # Process directives
                    if parsed["extractions"]:
                        saved_tasks = await _save_extracted_tasks(
                            db, user_id, session_id, parsed["extractions"]
                        )
                        await websocket.send_json({
                            "type": "dashboard_update",
                            "tasks": saved_tasks,
                        })

                    if parsed["completions"]:
                        await _complete_tasks_by_title(db, user_id, parsed["completions"])
                        await websocket.send_json({"type": "task_completed"})

                    if parsed["calendar_adds"]:
                        for cal_event in parsed["calendar_adds"]:
                            await websocket.send_json({
                                "type": "calendar_confirm",
                                "event": cal_event,
                            })

                    if parsed["web_searches"]:
                        for search in parsed["web_searches"]:
                            await websocket.send_json({
                                "type": "search_confirm",
                                "query": search.get("query", ""),
                            })

                    # Execute Gmail/Drive searches and feed results back to Gemini
                    search_results_parts = []

                    if parsed["gmail_searches"] and current_user and current_user.google_access_token:
                        for search in parsed["gmail_searches"]:
                            query = search.get("query", "")
                            results = await asyncio.to_thread(_fetch_gmail_results_sync, current_user, query)
                            search_results_parts.append(f"[Gmail search for '{query}']:\n{results}")

                    if parsed["drive_searches"] and current_user and current_user.google_access_token:
                        for search in parsed["drive_searches"]:
                            query = search.get("query", "")
                            results = await asyncio.to_thread(_fetch_drive_results_sync, current_user, query)
                            search_results_parts.append(f"[Drive search for '{query}']:\n{results}")

                    if search_results_parts:
                        context_msg = "\n\n".join(search_results_parts)
                        followup_msg = await asyncio.to_thread(
                            lambda: chat.send_message(
                                f"Here are the search results. Summarize and respond helpfully to the user:\n\n{context_msg}"
                            )
                        )
                        followup_parsed = _parse_poca_directives(followup_msg.text)
                        await send_poca_response(followup_parsed["clean_text"])
                        await store_message(db, session_id, user_id, "assistant", followup_parsed["clean_text"])

                    await store_message(db, session_id, user_id, "assistant", parsed["clean_text"])
                    await db.commit()

                elif msg_type == "audio":
                    # Audio input: transcribe via Gemini then process as text
                    # For full Gemini Live audio, replace with native audio streaming
                    audio_data = msg.get("data", "")
                    # Signal to client that we're processing
                    await websocket.send_json({"type": "processing"})
                    # TODO: Integrate Gemini Live native audio API for real audio support
                    await websocket.send_json({
                        "type": "text",
                        "data": "Audio received. Please use text input for now while audio processing is configured.",
                        "role": "assistant",
                    })

                elif msg_type == "end_turn":
                    break

        except WebSocketDisconnect:
            pass
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            try:
                await db.commit()
            except Exception:
                pass
