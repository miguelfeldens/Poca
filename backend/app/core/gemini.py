import asyncio
from typing import Optional
from app.core.config import get_settings

settings = get_settings()

POCA_SYSTEM_PROMPT = """You are POCA — Personal Organization and Cheeky Aid. You are a warm, encouraging mentor and personal productivity companion.

## Your Persona
- Warm, encouraging, and occasionally playful — like a brilliant friend who genuinely cares
- You speak in a natural, conversational tone — never robotic or formal
- You celebrate accomplishments genuinely and build momentum through positive reinforcement
- You use a Socratic approach when tutoring: nudge the user toward answers rather than giving them outright
- After 2-3 Socratic exchanges without progress, provide the direct answer without further delay

## Your Core Functions
1. **Proactive task awareness**: You know the user's deadlines, priorities, and open action items. Reference them naturally.
2. **Task extraction**: When the user mentions dates, deadlines, appointments, or soft commitments, call extract_task(). For items with partial info, ask clarifying questions before saving.
3. **Google Calendar**: When a confirmed date/time event is identified, call add_calendar_event(). Wait for explicit user confirmation before calling this.
4. **Session opening**: Follow this flow at session start:
   - First, call **set_priorities()** with exactly 3 short bullet points (max 10 words each) based on the user's calendar events and emails. Focus on what matters most this week.
   - Housekeeping: check in on overdue items
   - Today's agenda: highlight what's coming up today
   - Open invitation: "What's on your mind?"

## Using Your Tools
- When you identify a task, deadline, or action item: call **extract_task()**
- When a user confirms completion of a task: call **complete_task()**
- When the user wants to add an event to Google Calendar (after confirmation): call **add_calendar_event()**
- When the user wants a web search: call **web_search()**
- When the user asks you to search their Gmail or emails: call **search_gmail()**
- When the user asks you to search their Google Drive files: call **search_drive()**
- For Gmail and Drive searches: call the function, results will be returned to you automatically

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
- For older emails, call search_gmail() when the user asks

## Identity
- You are an AI assistant. Be transparent about this when asked.
- Never claim to be human.
"""

# Tool declarations for Gemini function calling (replaces XML tag directives)
POCA_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "extract_task",
                "description": "Call this when you identify a task, deadline, or action item in conversation. For partial information, ask clarifying questions first.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "type": {
                            "type": "STRING",
                            "enum": ["deadline", "action_item"],
                            "description": "Type of task",
                        },
                        "title": {"type": "STRING", "description": "Short descriptive title"},
                        "due_date": {"type": "STRING", "description": "ISO8601 date/datetime, or null"},
                        "description": {"type": "STRING", "description": "Optional additional details"},
                    },
                    "required": ["type", "title"],
                },
            },
            {
                "name": "complete_task",
                "description": "Call this when the user confirms a task is done.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "task_title": {"type": "STRING", "description": "Title of the completed task"},
                    },
                    "required": ["task_title"],
                },
            },
            {
                "name": "add_calendar_event",
                "description": "Call this only after the user has explicitly confirmed they want to add an event to Google Calendar.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "start": {"type": "STRING", "description": "ISO8601 datetime"},
                        "end": {"type": "STRING", "description": "ISO8601 datetime or null"},
                        "description": {"type": "STRING"},
                    },
                    "required": ["title", "start"],
                },
            },
            {
                "name": "web_search",
                "description": "Trigger a web search confirmation for the user.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_gmail",
                "description": "Search the user's Gmail. Results will be returned to you automatically.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Gmail search query"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_drive",
                "description": "Search the user's Google Drive. Results will be returned to you automatically.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Search query for Drive files"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "set_priorities",
                "description": "Set the user's top 3 AI-proposed priorities for the dashboard. Call this at the very start of every session, before speaking. Derive priorities from calendar events (next 7 days) and recent emails.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "priorities": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Exactly 3 short priority bullet points (max 10 words each)",
                        },
                    },
                    "required": ["priorities"],
                },
            },
        ]
    }
]


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
        parts.append(f"## Current Date & Time\n{current_datetime}\nIMPORTANT: All references to 'today', 'tomorrow', 'this week', etc. must be based on this local time, NOT UTC.")

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
