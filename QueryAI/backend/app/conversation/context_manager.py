"""
QueryAI — Conversation Context Manager.

Rebuilds ConversationMemory from QueryHistory records and provides
compact context for the LLM prompt. Does NOT blindly dump the
full conversation — extracts only relevant entities.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.conversation.memory import ConversationMemory
from app.models.history import QueryHistory, QueryStatus, Conversation
from app.core.logging import get_logger

log = get_logger(__name__)

# Cache recent memories to avoid repeated DB hits within the same request
_memory_cache: dict[str, ConversationMemory] = {}


def get_conversation_memory(
    db: Session,
    conversation_id: uuid.UUID,
    max_turns: int = 5,
) -> ConversationMemory:
    """
    Build a ConversationMemory from the last N successful turns.

    Returns a fresh ConversationMemory if the conversation is new or empty.
    """
    cache_key = str(conversation_id)
    if cache_key in _memory_cache:
        return _memory_cache[cache_key]

    memory = ConversationMemory(conversation_id=cache_key)

    try:
        recent = (
            db.query(QueryHistory)
            .filter(
                QueryHistory.conversation_id == conversation_id,
                QueryHistory.status.in_([QueryStatus.SUCCESS, QueryStatus.CORRECTED]),
            )
            .order_by(QueryHistory.created_at.desc())
            .limit(max_turns)
            .all()
        )

        # Process oldest-first so memory accumulates correctly
        for qh in reversed(recent):
            sql = qh.corrected_sql or qh.generated_sql
            memory.update_from_turn(
                question=qh.question,
                sql=sql,
                tables=qh.relevant_tables,
                viz_type=qh.visualization_type,
            )

        log.debug(
            "Conversation memory built",
            conversation_id=cache_key,
            turns=memory.turn_count,
            tables=memory.tables,
        )

    except Exception as exc:
        log.warning("Failed to build conversation memory", error=str(exc))

    # Cache for this request cycle
    _memory_cache[cache_key] = memory
    return memory


def invalidate_memory_cache(conversation_id: Optional[str] = None) -> None:
    """Clear cached memory. Call after a new turn is persisted."""
    if conversation_id:
        _memory_cache.pop(conversation_id, None)
    else:
        _memory_cache.clear()


def get_context_string(
    db: Session,
    conversation_id: uuid.UUID,
    max_turns: int = 5,
) -> str:
    """
    Convenience function: returns the compact context string
    ready for injection into the LLM prompt.
    """
    memory = get_conversation_memory(db, conversation_id, max_turns)
    return memory.to_context_string()
