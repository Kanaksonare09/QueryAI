"""
Conversation management API — CRUD for conversations and messages.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.models import Conversation, Message
from app.schemas.schemas import ConversationOut, ConversationDetail, MessageOut, Citation
import json

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationOut])
def list_conversations(db: Session = Depends(get_db)):
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    result = []
    for c in convs:
        count = db.query(Message).filter(Message.conversation_id == c.id).count()
        result.append(ConversationOut(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=count,
        ))
    return result


@router.get("/{conv_id}", response_model=ConversationDetail)
def get_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    msg_count = len(messages)

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=msg_count,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                sources=[Citation(**s) for s in (m.sources or [])],
                sql_queries=m.sql_queries,
                tools_used=m.tools_used,
                chart_data=m.chart_data,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.patch("/{conv_id}/title")
def rename_conversation(conv_id: str, title: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.title = title[:200]
    db.commit()
    return {"message": "Title updated"}


@router.delete("/{conv_id}")
def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted"}
