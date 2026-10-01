"""
PolicyPilot — Flask Auth Decorators
"""
from __future__ import annotations

from functools import wraps
from typing import Callable, Optional

from flask import g, jsonify, request

from backend.auth.jwt_handler import decode_access_token, role_has_access
from backend.config import get_logger

logger = get_logger(__name__)


def _extract_token() -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # Also check cookie for browser-based pages
    return request.cookies.get("access_token")


def login_required(f: Callable) -> Callable:
    """Decorator: requires a valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authentication required", "code": "AUTH_REQUIRED"}), 401

        payload = decode_access_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token", "code": "AUTH_INVALID"}), 401

        g.user_id = payload["sub"]
        g.user_email = payload["email"]
        g.user_role = payload["role"]
        return f(*args, **kwargs)
    return decorated


def role_required(minimum_role: str) -> Callable:
    """Decorator factory: requires user to have at least minimum_role."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            if not role_has_access(g.user_role, minimum_role):
                logger.warning(
                    "access_denied",
                    user_id=g.user_id,
                    user_role=g.user_role,
                    required_role=minimum_role,
                )
                return jsonify({
                    "error": "Insufficient permissions",
                    "code": "FORBIDDEN",
                    "required_role": minimum_role,
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
