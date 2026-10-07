"""
SQLAlchemy models for application metadata storage.
(Conversations, documents index, etc. — stored in MySQL)
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean,
    Float, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship, declarative_base
import uuid
import enum

Base = declarative_base()


def gen_uuid() -> str:
    return str(uuid.uuid4())


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class Document(Base):
    __tablename__ = "app_documents"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String(1000), nullable=False)
    collection_id = Column(String(36), ForeignKey("app_collections.id"), nullable=True)
    status = Column(SAEnum(DocumentStatus), default=DocumentStatus.pending)
    chunk_count = Column(Integer, default=0)
    page_count = Column(Integer, default=0)
    category = Column(String(100), nullable=True)
    summary = Column(Text, nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    indexed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    collection = relationship("DocumentCollection", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentCollection(Base):
    __tablename__ = "app_collections"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    color = Column(String(20), default="#6366f1")
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="collection")


class DocumentChunk(Base):
    __tablename__ = "app_document_chunks"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    document_id = Column(String(36), ForeignKey("app_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    section = Column(String(500), nullable=True)
    chroma_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")


class Conversation(Base):
    __tablename__ = "app_conversations"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    title = Column(String(500), default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "app_messages"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    conversation_id = Column(String(36), ForeignKey("app_conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)       # citations
    sql_queries = Column(JSON, nullable=True)   # generated SQL
    tools_used = Column(JSON, nullable=True)    # MCP/agent tools
    chart_data = Column(JSON, nullable=True)    # visualization data
    thinking = Column(Text, nullable=True)      # agent reasoning
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
