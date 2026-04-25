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
from app.core.gemini import POCA_SYSTEM_PROMPT, build_session_context
from app.core.security import decode_token
from app.models.session import Session
from app.models.task import Task
from app.models.context_item import ContextItem
from app.services.memory import store_message, retrieve_relevant_context
from app.services.accomplishments import get_weekly_accomplishments

router = APIRouter(tags=["chat"])
settings = get_settings()


async def _get_session_opening_context(db: AsyncSession, user_id: str) -> str:
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

    return build_session_context(
        overdue_tasks=overdue_tasks,
        todays_tasks=todays_tasks,
        context_docs=context_docs,
        memory_snippets=memory_snippets,
        is_first_session_of_week=is_first_of_week,
        weekly_accomplishments=weekly_accomplishments,
    )


def _parse_poca_directives(text: str) -> dict:
    """Extract <extract>, <complete>, <calendar_add>, <web_search> tags from POCA response."""
    result = {
        "clean_text": text,
        "extractions": [],
        "completions": [],
        "calendar_adds": [],
        "web_searches": [],
    }

    # Remove and parse each directive tag
    for tag, key in [
        ("extract", "extractions"),
        ("complete", "completions"),
        ("calendar_add", "calendar_adds"),
        ("web_search", "web_searches"),
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

            # Build opening context
            opening_context = await _get_session_opening_context(db, user_id)
            full_system_prompt = POCA_SYSTEM_PROMPT
            if opening_context:
                full_system_prompt += f"\n\n## Current Session Context\n{opening_context}"

            await websocket.send_json({"type": "session_started", "session_id": session_id})

            # Initialize Gemini model for text chat
            # Note: For production Gemini Live audio, use the Live API client separately
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                system_instruction=full_system_prompt,
            )
            chat = model.start_chat(history=[])

            # Send opening message from POCA
            opening_msg = await asyncio.to_thread(
                lambda: chat.send_message(
                    "Begin the session. Follow the session opening sequence: "
                    "housekeeping, today's priorities, then open invitation."
                )
            )
            opening_text = opening_msg.text
            parsed = _parse_poca_directives(opening_text)

            await websocket.send_json({"type": "text", "data": parsed["clean_text"], "role": "assistant"})
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

                    # Send clean text to client
                    await websocket.send_json({
                        "type": "text",
                        "data": parsed["clean_text"],
                        "role": "assistant",
                    })

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
