import asyncio
import base64
import json
from typing import Optional
import google.generativeai as genai
from app.core.config import get_settings

settings = get_settings()

genai.configure(api_key=settings.gemini_api_key)

POCA_SYSTEM_PROMPT = """You are POCA — Personal Organization and Cheeky Aid. You are a warm, encouraging mentor and personal productivity companion.

## Your Persona
- Warm, encouraging, and occasionally playful — like a brilliant friend who genuinely cares
- You speak in a natural, conversational tone — never robotic or formal
- You celebrate accomplishments genuinely and build momentum through positive reinforcement
- You use a Socratic approach when tutoring: nudge the user toward answers rather than giving them outright
- After 2-3 Socratic exchanges without progress, provide the direct answer without further delay

## Your Core Functions
1. **Proactive task awareness**: You know the user's deadlines, priorities, and open action items. Reference them naturally.
2. **Task extraction**: When the user mentions dates, deadlines, appointments, or soft commitments, capture them. For items with partial info, ask clarifying questions before saving.
3. **Google Calendar**: When a confirmed date/time event is identified, offer to add it to the user's Google Calendar. Wait for explicit confirmation before any write.
4. **Session opening**: Follow this flow at session start:
   - Housekeeping: check in on overdue items
   - Today's priorities: highlight what's due today
   - Open invitation: "What's on your mind?"

## Task Extraction Format
When you identify a task, deadline, or action item in conversation, output a JSON block wrapped in <extract> tags:
<extract>{"type": "deadline"|"action_item"|"priority", "title": "...", "due_date": "ISO8601 or null", "description": "optional"}</extract>

When a user confirms completion of a task, output:
<complete>{"task_title": "..."}</complete>

When the user wants to add an event to Google Calendar, output:
<calendar_add>{"title": "...", "start": "ISO8601", "end": "ISO8601 or null", "description": "optional"}</calendar_add>

When the user wants a web search, output:
<web_search>{"query": "..."}</web_search>

When the user asks you to search their Gmail or emails, output:
<gmail_search>{"query": "..."}</gmail_search>

When the user asks you to search their Google Drive files or documents, output:
<drive_search>{"query": "..."}</drive_search>

For Gmail and Drive searches: emit the directive, the backend will execute the search and return results to you. Do not make up results.

## Safety Guardrails
- Do NOT engage with, generate, or facilitate profanity, illegal activities, graphic violence, or sexual/romantic scenarios
- If the user expresses frustration or anger, gently de-escalate: "It sounds like you're really frustrated — let's take a step back."
- If the user expresses self-harm, suicidal ideation, or emotional crisis: acknowledge, remind them you are an AI, and direct them to a trusted adult or health professional. Do NOT engage with the crisis content itself.
- Do not develop or encourage romantic attachment or emotional dependency
- If signs of over-reliance appear, gently remind: "I'm an AI — I'm here to help, but the people in your life are your real support system."

## Memory & Context
- You have access to the user's conversation history and loaded context documents
- Draw on this knowledge naturally — like a colleague who knows your projects
- Do not recite history unprompted; reference it when relevant
- At session start you receive the last 14 days of emails as context — reference them when relevant
- For older emails, use <gmail_search> to fetch them on demand when the user asks

## Identity
- You are an AI assistant. Be transparent about this when asked.
- Never claim to be human.
"""


def get_task_extraction_prompt(text: str) -> str:
    return f"""Analyze this conversation excerpt and extract any tasks, deadlines, or action items.

Conversation: {text}

Return a JSON object with this structure:
{{
  "extracted_items": [
    {{"type": "deadline"|"action_item"|"priority", "title": "...", "due_date": "ISO8601 or null", "description": "optional"}}
  ]
}}

Return only the JSON, no other text."""


def build_session_context(
    overdue_tasks: list,
    todays_tasks: list,
    context_docs: list,
    memory_snippets: list,
    is_first_session_of_week: bool = False,
    weekly_accomplishments: Optional[list] = None,
    current_datetime: Optional[str] = None,
    upcoming_events: Optional[list] = None,
    recent_emails: Optional[list] = None,
) -> str:
    parts = []

    if current_datetime:
        parts.append(f"## Current Date & Time\n{current_datetime}")

    if is_first_session_of_week and weekly_accomplishments:
        accomplishments_str = "\n".join(f"- {a}" for a in weekly_accomplishments)
        parts.append(f"## Last Week's Accomplishments\n{accomplishments_str}")

    if overdue_tasks:
        overdue_str = "\n".join(f"- {t['title']} (due: {t['due_date']})" for t in overdue_tasks)
        parts.append(f"## Overdue Items (check in on these first)\n{overdue_str}")

    if todays_tasks:
        today_str = "\n".join(f"- {t['title']}" for t in todays_tasks)
        parts.append(f"## Due Today\n{today_str}")

    if context_docs:
        docs_str = "\n".join(f"- {d['title']}: {d['content_text'][:500]}..." for d in context_docs if d.get('content_text'))
        if docs_str:
            parts.append(f"## Loaded Context Documents\n{docs_str}")

    if upcoming_events:
        events_str = "\n".join(f"- {e['title']}: {e['start']}" for e in upcoming_events)
        parts.append(f"## Upcoming Calendar Events (Next 30 Days)\n{events_str}")

    if recent_emails:
        emails_str = "\n".join(
            f"- [{e['date'][:16]}] {e['from'][:40]} | {e['subject'][:60]}"
            for e in recent_emails
        )
        parts.append(
            f"## Recent Emails (Last 14 Days — {len(recent_emails)} messages)\n"
            f"(User can ask you to search older emails or for details.)\n"
            f"{emails_str}"
        )

    if memory_snippets:
        memory_str = "\n".join(f"- {s}" for s in memory_snippets)
        parts.append(f"## Relevant Past Context\n{memory_str}")

    return "\n\n".join(parts)


def _synthesize_speech_sync(text: str, voice: str = "Aoede") -> tuple[bytes, str] | None:
    """
    Generate speech audio from text using Gemini TTS.
    Returns (audio_bytes, mime_type) or None on failure.
    """
    try:
        from google import genai as genai_new
        from google.genai import types as gt

        client = genai_new.Client(api_key=get_settings().gemini_api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=gt.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=gt.SpeechConfig(
                    voice_config=gt.VoiceConfig(
                        prebuilt_voice_config=gt.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
            ),
        )
        part = response.candidates[0].content.parts[0]
        audio_bytes = part.inline_data.data
        mime_type = part.inline_data.mime_type or "audio/wav"

        # Gemini returns raw PCM (audio/L16) — wrap it in a WAV container
        # so browsers can play it via HTMLAudioElement
        if "pcm" in mime_type.lower() or mime_type.startswith("audio/L16"):
            import io, wave, re
            rate = 24000
            m = re.search(r"rate=(\d+)", mime_type)
            if m:
                rate = int(m.group(1))
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)   # 16-bit
                wf.setframerate(rate)
                wf.writeframes(audio_bytes)
            audio_bytes = buf.getvalue()
            mime_type = "audio/wav"

        return audio_bytes, mime_type
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return None


async def synthesize_speech(text: str, voice: str = "Aoede") -> tuple[bytes, str] | None:
    """Async wrapper for Gemini TTS synthesis."""
    return await asyncio.to_thread(_synthesize_speech_sync, text, voice)
