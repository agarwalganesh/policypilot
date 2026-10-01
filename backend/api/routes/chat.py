"""
PolicyPilot — Chat Routes
POST /chat       — standard chat
POST /chat/stream — streaming response (SSE)
GET  /chat/conversations — list conversations
GET  /chat/conversations/<id>/messages
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Generator

from flask import Blueprint, Response, g, jsonify, request, stream_with_context

from backend.agents.graph import run_agent
from backend.auth.decorators import login_required
from backend.config import get_logger, bind_request_context
from backend.database import get_db, Conversation, Message, AuditLog
from backend.models.schemas import ChatRequest

logger = get_logger(__name__)
chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


def _get_or_create_conversation(db, user_id: str, conversation_id: str = None, title: str = None) -> Conversation:
    if conversation_id:
        conv = db.query(Conversation).filter_by(id=conversation_id, user_id=user_id).first()
        if conv:
            return conv
    conv = Conversation(user_id=user_id, title=title or "New Conversation")
    db.add(conv)
    db.flush()
    return conv


def _get_conversation_history(db, conversation_id: str, limit: int = 10) -> list:
    messages = (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


@chat_bp.post("")
@login_required
def chat():
    """
    Main chat endpoint.
    Runs the full LangGraph agent and returns the complete response.
    """
    rid = bind_request_context(user_id=g.user_id)

    try:
        data = ChatRequest.model_validate(request.get_json(force=True))
    except Exception as exc:
        return jsonify({"error": str(exc), "code": "VALIDATION_ERROR"}), 422

    with get_db() as db:
        # Get or create conversation
        conv = _get_or_create_conversation(db, g.user_id, data.conversation_id, data.query[:60])
        history = _get_conversation_history(db, str(conv.id))

        # Save user message
        user_msg = Message(
            conversation_id=str(conv.id),
            role="user",
            content=data.query,
        )
        db.add(user_msg)
        db.flush()

        # Run the LangGraph agent
        result = run_agent(
            query=data.query,
            user_id=g.user_id,
            user_role=g.user_role,
            conversation_id=str(conv.id),
            conversation_history=history,
        )

        # Save assistant message
        assistant_msg = Message(
            conversation_id=str(conv.id),
            role="assistant",
            content=result.get("answer", ""),
            sources=result.get("sources"),
            decision=result.get("decision"),
            confidence=result.get("final_confidence"),
            retry_count=result.get("retry_count", 0),
            latency_ms=result.get("latency_ms", 0),
        )
        db.add(assistant_msg)

        # Audit log
        audit = AuditLog(
            user_id=g.user_id,
            conversation_id=str(conv.id),
            query=data.query,
            decision=result.get("decision"),
            sources=result.get("sources"),
            retry_count=result.get("retry_count", 0),
            latency_ms=result.get("latency_ms", 0),
            agent_trace_id=result.get("agent_trace_id"),
        )
        db.add(audit)

        # Update conversation title from first message
        if not data.conversation_id:
            conv.title = data.query[:80]

        db.flush()

        return jsonify({
            "conversation_id": str(conv.id),
            "message_id": str(assistant_msg.id),
            "query": data.query,
            "answer": result.get("answer", ""),
            "decision": result.get("decision", "REFUSE"),
            "confidence": result.get("final_confidence", 0.0),
            "sources": result.get("sources", []),
            "retry_count": result.get("retry_count", 0),
            "latency_ms": result.get("latency_ms", 0),
            "debug_info": result.get("debug_info"),
        })


@chat_bp.post("/stream")
@login_required
def chat_stream():
    """
    Streaming chat endpoint using Server-Sent Events.
    Runs agent then streams the response token by token.
    """
    try:
        data = ChatRequest.model_validate(request.get_json(force=True))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 422

    def generate() -> Generator[str, None, None]:
        with get_db() as db:
            conv = _get_or_create_conversation(db, g.user_id, data.conversation_id, data.query[:60])
            history = _get_conversation_history(db, str(conv.id))

            db.add(Message(conversation_id=str(conv.id), role="user", content=data.query))
            db.flush()

            # Run agent (non-streaming — stream the result after)
            result = run_agent(
                query=data.query,
                user_id=g.user_id,
                user_role=g.user_role,
                conversation_id=str(conv.id),
                conversation_history=history,
            )

            answer = result.get("answer", "")
            # Stream answer word by word for UI effect
            words = answer.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                time.sleep(0.02)

            # Final metadata event
            yield f"data: {json.dumps({'type': 'done', 'decision': result.get('decision'), 'confidence': result.get('final_confidence', 0), 'sources': result.get('sources', []), 'conversation_id': str(conv.id), 'debug_info': result.get('debug_info')})}\n\n"

            # Save to DB
            assistant_msg = Message(
                conversation_id=str(conv.id),
                role="assistant",
                content=answer,
                sources=result.get("sources"),
                decision=result.get("decision"),
                confidence=result.get("final_confidence"),
                retry_count=result.get("retry_count", 0),
                latency_ms=result.get("latency_ms", 0),
            )
            db.add(assistant_msg)
            db.add(AuditLog(
                user_id=g.user_id,
                conversation_id=str(conv.id),
                query=data.query,
                decision=result.get("decision"),
                sources=result.get("sources"),
                retry_count=result.get("retry_count", 0),
                latency_ms=result.get("latency_ms", 0),
            ))

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@chat_bp.get("/conversations")
@login_required
def list_conversations():
    """List all conversations for the current user."""
    with get_db() as db:
        convs = (
            db.query(Conversation)
            .filter_by(user_id=g.user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(50)
            .all()
        )
        return jsonify([{
            "id": str(c.id),
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "message_count": len(c.messages),
        } for c in convs])


@chat_bp.get("/conversations/<conversation_id>/messages")
@login_required
def get_messages(conversation_id: str):
    """Get all messages for a conversation."""
    with get_db() as db:
        conv = db.query(Conversation).filter_by(id=conversation_id, user_id=g.user_id).first()
        if not conv:
            return jsonify({"error": "Conversation not found"}), 404

        return jsonify([{
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "decision": m.decision,
            "confidence": m.confidence,
            "latency_ms": m.latency_ms,
            "created_at": m.created_at.isoformat(),
        } for m in conv.messages])
