"""
PolicyPilot — Auth Routes
POST /auth/login
POST /auth/register
GET  /auth/me
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from backend.auth import (
    create_access_token, hash_password, login_required, verify_password,
)
from backend.config import get_logger, get_settings
from backend.database import get_db, User
from backend.models.schemas import LoginRequest, RegisterRequest

logger = get_logger(__name__)
settings = get_settings()
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.post("/register")
def register():
    """Register a new user."""
    try:
        data = RegisterRequest.model_validate(request.get_json(force=True))
    except Exception as exc:
        return jsonify({"error": str(exc), "code": "VALIDATION_ERROR"}), 422

    with get_db() as db:
        existing = db.query(User).filter_by(email=data.email).first()
        if existing:
            return jsonify({"error": "Email already registered", "code": "EMAIL_EXISTS"}), 409

        user = User(
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
        )
        db.add(user)
        db.flush()

        token = create_access_token(str(user.id), user.email, user.role)
        logger.info("user_registered", user_id=str(user.id), role=user.role)

        return jsonify({
            "access_token": token,
            "token_type": "bearer",
            "expires_in": settings.jwt_expiry_hours * 3600,
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role,
            },
        }), 201


@auth_bp.post("/login")
def login():
    """Authenticate user and return JWT token."""
    try:
        data = LoginRequest.model_validate(request.get_json(force=True))
    except Exception as exc:
        return jsonify({"error": str(exc), "code": "VALIDATION_ERROR"}), 422

    with get_db() as db:
        user = db.query(User).filter_by(email=data.email, is_active=True).first()
        if not user or not verify_password(data.password, user.password_hash):
            return jsonify({"error": "Invalid credentials", "code": "AUTH_FAILED"}), 401

        token = create_access_token(str(user.id), user.email, user.role)
        logger.info("user_login", user_id=str(user.id))

        return jsonify({
            "access_token": token,
            "token_type": "bearer",
            "expires_in": settings.jwt_expiry_hours * 3600,
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            },
        })


@auth_bp.get("/me")
@login_required
def me():
    """Return current user info."""
    with get_db() as db:
        user = db.query(User).filter_by(id=g.user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
        })
