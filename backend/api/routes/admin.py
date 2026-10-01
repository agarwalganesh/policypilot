"""
PolicyPilot — Admin Routes
GET /admin/analytics
GET /admin/audit-logs
GET /admin/users
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from backend.auth.decorators import role_required
from backend.config import get_logger
from backend.database import get_db, AuditLog, Document, DocumentVersion, Message, User

logger = get_logger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/analytics")
@role_required("admin")
def analytics():
    """Return platform-wide analytics."""
    with get_db() as db:
        total_docs = db.query(Document).count()
        active_policies = db.query(DocumentVersion).filter_by(status="active").count()
        archived_policies = db.query(DocumentVersion).filter_by(status="archived").count()

        total_queries = db.query(AuditLog).count()
        answered = db.query(AuditLog).filter_by(decision="ANSWER").count()
        refused = db.query(AuditLog).filter_by(decision="REFUSE").count()

        avg_latency = db.query(func.avg(AuditLog.latency_ms)).scalar()
        retrieval_success = (answered / total_queries * 100) if total_queries > 0 else 0

        return jsonify({
            "total_documents": total_docs,
            "active_policies": active_policies,
            "archived_policies": archived_policies,
            "total_queries": total_queries,
            "answered_queries": answered,
            "refused_queries": refused,
            "avg_latency_ms": round(float(avg_latency), 1) if avg_latency else None,
            "retrieval_success_rate": round(retrieval_success, 1),
            "refusal_rate": round((refused / total_queries * 100), 1) if total_queries > 0 else 0,
        })


@admin_bp.get("/audit-logs")
@role_required("admin")
def audit_logs():
    """Return paginated audit logs."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    decision_filter = request.args.get("decision")

    with get_db() as db:
        q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
        if decision_filter:
            q = q.filter_by(decision=decision_filter)

        total = q.count()
        logs = q.offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": [{
                "id": str(log.id),
                "user_id": log.user_id,
                "query": log.query[:200],
                "decision": log.decision,
                "retry_count": log.retry_count,
                "latency_ms": log.latency_ms,
                "source_count": len(log.sources) if log.sources else 0,
                "created_at": log.created_at.isoformat(),
            } for log in logs],
        })


@admin_bp.get("/users")
@role_required("admin")
def list_users():
    """List all users."""
    with get_db() as db:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return jsonify([{
            "id": str(u.id),
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        } for u in users])


@admin_bp.get("/queries-over-time")
@role_required("admin")
def queries_over_time():
    """Return query counts grouped by day (last 30 days)."""
    with get_db() as db:
        rows = (
            db.query(
                func.date(AuditLog.created_at).label("date"),
                func.count().label("total"),
                func.sum(func.cast(AuditLog.decision == "ANSWER", db.bind.dialect.INTEGER_TYPE if hasattr(db.bind.dialect, 'INTEGER_TYPE') else func.cast(AuditLog.decision == "ANSWER", func.count().type))).label("answered"),
            )
            .group_by(func.date(AuditLog.created_at))
            .order_by(func.date(AuditLog.created_at).desc())
            .limit(30)
            .all()
        )
        return jsonify([{
            "date": str(r.date),
            "total": r.total,
        } for r in reversed(rows)])
