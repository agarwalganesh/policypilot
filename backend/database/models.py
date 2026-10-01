"""
PolicyPilot — SQLAlchemy ORM Models
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, Date, JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database.connection import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    name: str = Column(String(255), nullable=False)
    email: str = Column(String(255), unique=True, nullable=False, index=True)
    password_hash: str = Column(String(255), nullable=False)
    role: str = Column(String(50), nullable=False, default="employee")
    is_active: bool = Column(Boolean, default=True, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    name: str = Column(String(255), nullable=False)
    slug: str = Column(String(255), unique=True, nullable=False, index=True)
    category: Optional[str] = Column(String(100))
    department: Optional[str] = Column(String(100))
    description: Optional[str] = Column(Text)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")

    @property
    def active_version(self) -> Optional["DocumentVersion"]:
        for v in self.versions:
            if v.status == "active":
                return v
        return None


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    document_id: str = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version: Optional[str] = Column(String(50))
    status: str = Column(String(20), nullable=False, default="active")
    effective_date: Optional[date] = Column(Date)
    last_updated: Optional[date] = Column(Date)
    source_file: str = Column(String(500), nullable=False)
    file_hash: Optional[str] = Column(String(64))
    chunk_count: int = Column(Integer, default=0)
    indexed: bool = Column(Boolean, default=False, nullable=False)
    access_roles: List[str] = Column(JSON, default=list, nullable=False)
    uploaded_by: Optional[str] = Column(String(36), ForeignKey("users.id"))
    notes: Optional[str] = Column(Text)
    uploaded_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="versions")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class Conversation(Base):
    __tablename__ = "conversations"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    user_id: str = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Optional[str] = Column(String(500))
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    conversation_id: str = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role: str = Column(String(20), nullable=False)
    content: str = Column(Text, nullable=False)
    sources: Optional[dict] = Column(JSON)
    decision: Optional[str] = Column(String(20))
    confidence: Optional[float] = Column(Float)
    retry_count: int = Column(Integer, default=0)
    latency_ms: Optional[int] = Column(Integer)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    user_id: Optional[str] = Column(String(36), ForeignKey("users.id"))
    conversation_id: Optional[str] = Column(String(36), ForeignKey("conversations.id"))
    query: str = Column(Text, nullable=False)
    decision: Optional[str] = Column(String(20))
    sources: Optional[dict] = Column(JSON)
    retry_count: int = Column(Integer, default=0)
    latency_ms: Optional[int] = Column(Integer)
    agent_trace_id: Optional[str] = Column(String(255))
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="audit_logs")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    run_name: Optional[str] = Column(String(255))
    question: str = Column(Text, nullable=False)
    expected_answer: Optional[str] = Column(Text)
    actual_answer: Optional[str] = Column(Text)
    faithfulness_score: Optional[float] = Column(Float)
    relevance_score: Optional[float] = Column(Float)
    hallucination_score: Optional[float] = Column(Float)
    refusal_correct: Optional[bool] = Column(Boolean)
    should_answer: Optional[bool] = Column(Boolean)
    did_answer: Optional[bool] = Column(Boolean)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

