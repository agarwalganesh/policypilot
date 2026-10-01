from backend.database.connection import Base, engine, SessionLocal, get_db, health_check
from backend.database.models import (
    User, Document, DocumentVersion,
    Conversation, Message, AuditLog, EvaluationResult,
)

# Auto-create all tables once models are loaded into Base.metadata
Base.metadata.create_all(engine)

__all__ = [
    "Base", "engine", "SessionLocal", "get_db", "health_check",
    "User", "Document", "DocumentVersion",
    "Conversation", "Message", "AuditLog", "EvaluationResult",
]
