"""
Gemini Live API WebSocket proxy.

Protocol:
  Client → Server:
    {"type": "audio_chunk", "data": "<base64-pcm16>"}   # streaming mic audio at 16kHz
    {"type": "audio_end"}                                # end of user speech turn
    {"type": "text", "data": "message text"}             # keyboard input
    {"type": "end_turn"}                                 # close session

  Server → Client:
    {"type": "text", "data": "...", "role": "assistant"|"user"}
    {"type": "audio_response", "data": "<base64-wav>", "mime_type": "audio/wav"}
    {"type": "dashboard_update", "tasks": [...]}
    {"type": "calendar_confirm", "event": {...}}
    {"type": "search_confirm", "query": "..."}
    {"type": "task_completed"}
    {"type": "session_started", "session_id": "..."}
    {"type": "error", "message": "..."}
"""
import asyncio
import base64
import io
import json
import uuid
import wave
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.gemini import POCA_SYSTEM_PROMPT, POCA_TOOLS, build_session_context
from app.core.security import decode_token
from app.models.session import Session
from app.models.task import Task
from app.models.context_item import ContextItem
from app.models.user import User
from app.services.memory import store_message, retrieve_relevant_context
from app.services.accomplishments import get_weekly_accomplishments

router = APIRouter(tags=["chat"])
settings = get_settings()

OPENING_PROMPT = (
    "Begin the session. Follow the opening sequence: "
    "housekeeping (overdue items), today's priorities, then open invitation. "
    "Keep it concise — this is spoken aloud."
)


def _pcm_to_wav(pcm_bytes: bytes, rate: int = 24000) -> bytes:
    """Wrap raw PCM16 bytes in a WAV container so browsers can play it."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def _build_google_credentials(user: "User"):
    from google.oauth2.credentials import Credentials
    return Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def _fetch_calendar_events_sync(user: "User") -> list:
    try:
        from googleapiclient.discovery import build
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
        print(f"[Calendar] Error: {e}")
        return []


def _fetch_recent_emails_sync(user: "User", days: int = 14, max_results: int = 10) -> list:
    try:
        from googleapiclient.discovery import build
        creds = _build_google_credentials(user)
        service = build("gmail", "v1", credentials=creds)
        resp = service.users().messages().list(
            userId="me", q=f"newer_than:{days}d", maxResults=max_results,
        ).execute()
        emails = []
        for msg in resp.get("messages", []):
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            emails.append({
                "subject": headers.get("Subject", "N/A"),
                "from": headers.get("From", "N/A"),
                "date": headers.get("Date", "N/A"),
            })
        return emails
    except Exception as e:
        print(f"[Gmail] Error: {e}")
        return []


def _fetch_gmail_results_sync(user: "User", query: str) -> str:
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
            lines.append(
                f"- {headers.get('Subject','N/A')} | {headers.get('From','N/A')} | {headers.get('Date','N/A')}\n"
                f"  {detail.get('snippet','')[:200]}"
            )
        return "\n".join(lines)
    except Exception as e:
        print(f"[Gmail] Error: {e}")
        return f"Could not search Gmail: {e}"


def _fetch_drive_results_sync(user: "User", query: str) -> str:
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
        lines = [
            f"- {f['name']} — modified {f.get('modifiedTime','')[:10]} | {f.get('webViewLink','')}"
            for f in files
        ]
        return "\n".join(lines)
    except Exception as e:
        print(f"[Drive] Error: {e}")
        return f"Could not search Drive: {e}"


async def _get_session_opening_context(
    db: AsyncSession, user_id: str, local_datetime: str = None, user: "User" = None
) -> str:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    overdue_result = await db.execute(
        select(Task).where(and_(
            Task.user_id == user_id, Task.is_completed == False,
            Task.due_date < today_start, Task.task_type == "deadline",
        )).order_by(Task.due_date.asc()).limit(10)
    )
    overdue_tasks = [
        {"title": t.title, "due_date": t.due_date.strftime("%B %d") if t.due_date else "unknown"}
        for t in overdue_result.scalars().all()
    ]

    today_result = await db.execute(
        select(Task).where(and_(
            Task.user_id == user_id, Task.is_completed == False,
            Task.due_date >= today_start, Task.due_date < today_end,
        )).order_by(Task.due_date.asc()).limit(10)
    )
    todays_tasks = [{"title": t.title} for t in today_result.scalars().all()]

    ctx_result = await db.execute(
        select(ContextItem).where(and_(
            ContextItem.user_id == user_id,
            (ContextItem.auto_expires_at == None) | (ContextItem.auto_expires_at > now),
        )).limit(20)
    )
    context_docs = [{"title": c.title, "content_text": c.content_text} for c in ctx_result.scalars().all()]

    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    session_result = await db.execute(
        select(Session).where(and_(Session.user_id == user_id, Session.session_start >= week_start)).limit(1)
    )
    is_first_of_week = session_result.scalar_one_or_none() is None
    weekly_accomplishments = await get_weekly_accomplishments(db, user_id) if is_first_of_week else []

    memory_snippets = await retrieve_relevant_context(
        db, user_id, "what are the user's current projects and priorities", top_k=8
    )

    current_dt = local_datetime or now.strftime("%A, %B %d, %Y — %I:%M %p UTC")

    upcoming_events, recent_emails = [], []
    if user and user.google_access_token:
        results = await asyncio.gather(
            asyncio.wait_for(asyncio.to_thread(_fetch_calendar_events_sync, user), timeout=8),
            asyncio.wait_for(asyncio.to_thread(_fetch_recent_emails_sync, user), timeout=8),
            return_exceptions=True,
        )
        upcoming_events = results[0] if isinstance(results[0], list) else []
        recent_emails = results[1] if isinstance(results[1], list) else []

    return build_session_context(
        overdue_tasks=overdue_tasks, todays_tasks=todays_tasks, context_docs=context_docs,
        memory_snippets=memory_snippets, is_first_session_of_week=is_first_of_week,
        weekly_accomplishments=weekly_accomplishments, current_datetime=current_dt,
        upcoming_events=upcoming_events, recent_emails=recent_emails,
    )


async def _save_extracted_task(db: AsyncSession, user_id: str, session_id: str, args: dict) -> dict:
    task_type = args.get("type", "action_item")
    if task_type not in ("deadline", "action_item", "priority"):
        task_type = "action_item"
    due_date = None
    if args.get("due_date"):
        try:
            due_date = datetime.fromisoformat(args["due_date"])
        except ValueError:
            pass
    task = Task(
        user_id=uuid.UUID(user_id), session_id=uuid.UUID(session_id),
        title=args.get("title", "Untitled task"), description=args.get("description"),
        task_type=task_type, due_date=due_date,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return {
        "id": str(task.id), "title": task.title,
        "task_type": task.task_type,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }


async def _complete_task_by_title(db: AsyncSession, user_id: str, title: str):
    result = await db.execute(
        select(Task).where(and_(
            Task.user_id == user_id, Task.title.ilike(f"%{title}%"), Task.is_completed == False,
        )).limit(1)
    )
    task = result.scalar_one_or_none()
    if task:
        task.is_completed = True


async def _handle_tool_call(
    fc, db: AsyncSession, session_id: str, user_id: str,
    websocket: WebSocket, current_user: Optional["User"],
) -> dict:
    """Dispatch a Gemini function call to the appropriate handler."""
    name = fc.name
    args = dict(fc.args) if fc.args else {}

    if name == "extract_task":
        saved = await _save_extracted_task(db, user_id, session_id, args)
        await db.commit()
        await websocket.send_json({"type": "dashboard_update", "tasks": [saved]})
        return {"saved": True}

    elif name == "complete_task":
        await _complete_task_by_title(db, user_id, args.get("task_title", ""))
        await db.commit()
        await websocket.send_json({"type": "task_completed"})
        return {"completed": True}

    elif name == "add_calendar_event":
        await websocket.send_json({"type": "calendar_confirm", "event": args})
        return {"pending_confirmation": True}

    elif name == "web_search":
        await websocket.send_json({"type": "search_confirm", "query": args.get("query", "")})
        return {"queued": True}

    elif name == "search_gmail":
        if current_user and current_user.google_access_token:
            results = await asyncio.to_thread(_fetch_gmail_results_sync, current_user, args.get("query", ""))
        else:
            results = "Gmail access not available."
        return {"results": results}

    elif name == "search_drive":
        if current_user and current_user.google_access_token:
            results = await asyncio.to_thread(_fetch_drive_results_sync, current_user, args.get("query", ""))
        else:
            results = "Drive access not available."
        return {"results": results}

    return {}


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    local_datetime: Optional[str] = Query(None),
):
    """WebSocket endpoint — proxies to Gemini Live API for true speech-to-speech."""
    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Session).where(and_(Session.id == session_id, Session.user_id == user_id))
            )
            if not result.scalar_one_or_none():
                await websocket.send_json({"type": "error", "message": "Session not found"})
                await websocket.close()
                return

            user_result = await db.execute(select(User).where(User.id == user_id))
            current_user = user_result.scalar_one_or_none()

            opening_context = await _get_session_opening_context(db, user_id, local_datetime, user=current_user)
            full_system_prompt = POCA_SYSTEM_PROMPT
            if opening_context:
                full_system_prompt += f"\n\n## Current Session Context\n{opening_context}"

            await websocket.send_json({"type": "session_started", "session_id": session_id})

            voice = (current_user.voice_preference if current_user and current_user.voice_preference else "Aoede")

            from google import genai as genai_live
            from google.genai import types as gt

            client = genai_live.Client(
                api_key=settings.gemini_api_key,
            )

            live_config = gt.LiveConnectConfig(
                response_modalities=["AUDIO"],
                system_instruction=full_system_prompt,
                tools=POCA_TOOLS,
                speech_config=gt.SpeechConfig(
                    voice_config=gt.VoiceConfig(
                        prebuilt_voice_config=gt.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
                input_audio_transcription=gt.AudioTranscriptionConfig(),
                output_audio_transcription=gt.AudioTranscriptionConfig(),
            )

            async with client.aio.live.connect(
                model="gemini-2.5-flash-native-audio-latest",
                config=live_config,
            ) as live:
                # Kick off the session opening sequence
                await live.send(input=OPENING_PROMPT, end_of_turn=True)

                t1 = asyncio.create_task(_frontend_to_live(websocket, live))
                t2 = asyncio.create_task(
                    _live_to_frontend(websocket, live, db, session_id, user_id, current_user)
                )
                try:
                    await asyncio.gather(t1, t2)
                finally:
                    t1.cancel()
                    t2.cancel()
                    await asyncio.gather(t1, t2, return_exceptions=True)

        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[chat] Error: {e}")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            try:
                await db.commit()
            except Exception:
                pass


async def _frontend_to_live(websocket: WebSocket, live) -> None:
    """Forward WebSocket messages from frontend to Gemini Live session."""
    from google.genai import types as gt

    try:
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

            if msg_type == "audio_chunk":
                pcm_bytes = base64.b64decode(msg.get("data", ""))
                if pcm_bytes:
                    await live.send(
                        input=gt.LiveClientRealtimeInput(
                            audio=gt.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                        )
                    )

            elif msg_type == "audio_end":
                await live.send(
                    input=gt.LiveClientRealtimeInput(activity_end=gt.ActivityEnd())
                )

            elif msg_type == "text":
                user_text = msg.get("data", "").strip()
                if user_text:
                    await live.send(input=user_text, end_of_turn=True)

            elif msg_type == "end_turn":
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[frontend_to_live] Error: {e}")


async def _live_to_frontend(
    websocket: WebSocket,
    live,
    db: AsyncSession,
    session_id: str,
    user_id: str,
    current_user: Optional["User"],
) -> None:
    """Stream Gemini Live API responses back to the frontend."""
    from google.genai import types as gt

    accumulated_output_text = ""

    try:
        while True:
            async for response in live.receive():
                sc = response.server_content

            if sc:
                # Streaming audio chunks from POCA
                if sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            wav = _pcm_to_wav(part.inline_data.data)
                            await websocket.send_json({
                                "type": "audio_response",
                                "data": base64.b64encode(wav).decode(),
                                "mime_type": "audio/wav",
                            })

                # POCA's spoken words as text (output transcription)
                if sc.output_transcription:
                    text = getattr(sc.output_transcription, "text", "") or ""
                    if text:
                        accumulated_output_text += text

                # User's spoken words as text (input transcription)
                if sc.input_transcription:
                    user_text = getattr(sc.input_transcription, "text", "") or ""
                    if user_text:
                        await websocket.send_json({"type": "text", "data": user_text, "role": "user"})
                        await store_message(db, session_id, user_id, "user", user_text)
                        await db.commit()

                # Turn complete — flush accumulated transcript to frontend
                if sc.turn_complete:
                    if accumulated_output_text:
                        await websocket.send_json({
                            "type": "text",
                            "data": accumulated_output_text,
                            "role": "assistant",
                        })
                        await store_message(db, session_id, user_id, "assistant", accumulated_output_text)
                        await db.commit()
                        accumulated_output_text = ""
                    # Always signal turn end so frontend clears the typing/thinking state
                    await websocket.send_json({"type": "turn_complete"})

            # Function calls (directives)
            if response.tool_call:
                tool_responses = []
                for fc in response.tool_call.function_calls:
                    result = await _handle_tool_call(fc, db, session_id, user_id, websocket, current_user)
                    tool_responses.append(
                        gt.FunctionResponse(name=fc.name, id=fc.id, response=result)
                    )
                await live.send(
                    input=gt.LiveClientToolResponse(function_responses=tool_responses)
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[live_to_frontend] Error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
