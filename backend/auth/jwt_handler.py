"""
PolicyPilot — JWT Authentication & Password Hashing
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from backend.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()

# ── Role hierarchy ────────────────────────────────────────────
ROLE_HIERARCHY = {
    "employee": 1,
    "manager": 2,
    "hr": 3,
    "admin": 4,
}

VALID_ROLES = set(ROLE_HIERARCHY.keys())


def hash_password(plain: str) -> str:
    """Return bcrypt hash of the password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expiry_hours: Optional[int] = None,
) -> str:
    """Create a signed JWT access token."""
    hours = expiry_hours or settings.jwt_expiry_hours
    expire = datetime.now(timezone.utc) + timedelta(hours=hours)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT. Returns payload dict or None on failure.
    Never raises — callers should treat None as authentication failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except ExpiredSignatureError:
        logger.warning("jwt_expired")
        return None
    except InvalidTokenError as exc:
        logger.warning("jwt_invalid", error=str(exc))
        return None


def role_has_access(user_role: str, required_role: str) -> bool:
    """Return True if user_role satisfies the minimum required_role."""
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 999)
    return user_level >= required_level
