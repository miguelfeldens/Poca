"""
Persistent memory service using pgvector for semantic search over conversation history.
Uses Gemini text-embedding-004 to embed messages.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import google.generativeai as genai
import uuid

from app.core.config import get_settings
from app.models.conversation import ConversationMessage

settings = get_settings()


async def embed_text(content: str) -> Optional[List[float]]:
    """Generate an embedding vector using Gemini text-embedding-004."""
    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=content,
            task_type="retrieval_document",
        )
        return result["embedding"]
    except Exception:
        return None


async def store_message(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    role: str,
    content: str,
) -> ConversationMessage:
    """Store a conversation message with its embedding."""
    msg = ConversationMessage(
        session_id=uuid.UUID(session_id),
        user_id=uuid.UUID(user_id),
        role=role,
        content=content,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)

    # Store embedding in a separate pgvector operation
    embedding = await embed_text(content)
    if embedding:
        await db.execute(
            text("""
                INSERT INTO message_embeddings (message_id, user_id, embedding)
                VALUES (:msg_id, :user_id, :embedding)
            """),
            {
                "msg_id": str(msg.id),
                "user_id": user_id,
                "embedding": str(embedding),  # pgvector accepts list as string
            }
        )

    return msg


async def retrieve_relevant_context(
    db: AsyncSession,
    user_id: str,
    query: str,
    top_k: int = 10,
) -> List[str]:
    """Retrieve semantically relevant past messages for a query."""
    query_embedding = await embed_text(query)
    if not query_embedding:
        return []

    try:
        result = await db.execute(
            text("""
                SELECT cm.content, cm.role
                FROM message_embeddings me
                JOIN conversation_messages cm ON cm.id = me.message_id
                WHERE me.user_id = :user_id
                ORDER BY me.embedding <=> :embedding
                LIMIT :top_k
            """),
            {
                "user_id": user_id,
                "embedding": str(query_embedding),
                "top_k": top_k,
            }
        )
        rows = result.fetchall()
        return [f"[{row.role}]: {row.content}" for row in rows]
    except Exception:
        return []
