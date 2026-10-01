"""
PolicyPilot — Pydantic Request/Response Models
All API contracts are validated here — never trust raw request data.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["employee", "manager", "hr", "admin"] = "employee"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# Chat
# ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    conversation_id: Optional[str] = None
    stream: bool = False


class CitationSource(BaseModel):
    document_name: str
    document_id: Optional[str] = None
    version: Optional[str] = None
    effective_date: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    chunk_id: Optional[str] = None
    relevant_text: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    query: str
    answer: str
    decision: Literal["ANSWER", "REFUSE", "RETRIEVE_AGAIN"]
    confidence: float
    sources: List[CitationSource] = []
    retry_count: int = 0
    latency_ms: int = 0


# ─────────────────────────────────────────────────────────────
# Documents
# ─────────────────────────────────────────────────────────────

class DocumentUploadMetadata(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    category: Optional[str] = None
    department: Optional[str] = None
    version: Optional[str] = None
    effective_date: Optional[date] = None
    last_updated: Optional[date] = None
    status: Literal["active", "archived", "draft"] = "active"
    notes: Optional[str] = None
    access_roles: List[str] = ["employee", "manager", "hr", "admin"]


class DocumentVersionResponse(BaseModel):
    id: str
    document_id: str
    version: Optional[str]
    status: str
    effective_date: Optional[date]
    last_updated: Optional[date]
    source_file: str
    chunk_count: int
    indexed: bool
    access_roles: List[str]
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    name: str
    slug: str
    category: Optional[str]
    department: Optional[str]
    description: Optional[str]
    created_at: datetime
    versions: List[DocumentVersionResponse] = []

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# Conversations
# ─────────────────────────────────────────────────────────────

class ConversationResponse(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[List[CitationSource]]
    decision: Optional[str]
    confidence: Optional[float]
    latency_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────
# Evidence / Agent Internals
# ─────────────────────────────────────────────────────────────

class EvidenceDecision(BaseModel):
    sufficient: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    supporting_chunks: List[Dict[str, Any]] = []


class QueryAnalysis(BaseModel):
    intent: str
    category: Optional[str]
    entities: List[str] = []
    temporal_scope: Literal["current", "historical", "unknown"] = "current"
    requires_policy_evidence: bool = True
    potential_document_types: List[str] = []
    access_sensitivity: Literal["low", "medium", "high"] = "low"
    refined_query: Optional[str] = None


class AgentDecision(BaseModel):
    decision: Literal["ANSWER", "REFUSE", "RETRIEVE_AGAIN"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    sources: List[CitationSource] = []


# ─────────────────────────────────────────────────────────────
# Admin
# ─────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    query: str
    decision: Optional[str]
    retry_count: int
    latency_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalyticsResponse(BaseModel):
    total_documents: int
    active_policies: int
    archived_policies: int
    total_queries: int
    answered_queries: int
    refused_queries: int
    avg_latency_ms: Optional[float]
    retrieval_success_rate: Optional[float]
