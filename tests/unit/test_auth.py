"""
PolicyPilot — Unit Tests: Auth
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.auth.jwt_handler import (
    hash_password, verify_password,
    create_access_token, decode_access_token,
    role_has_access, ROLE_HIERARCHY,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        plain = "TestPassword123!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("CorrectPassword123!")
        assert not verify_password("WrongPassword123!", hashed)

    def test_hash_is_not_plaintext(self):
        plain = "MyPassword123!"
        hashed = hash_password(plain)
        assert plain not in hashed


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token("user-123", "test@pw.live", "employee")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@pw.live"
        assert payload["role"] == "employee"

    def test_invalid_token_returns_none(self):
        payload = decode_access_token("this.is.invalid")
        assert payload is None

    def test_tampered_token_returns_none(self):
        token = create_access_token("user-123", "test@pw.live", "employee")
        tampered = token[:-10] + "tampered!!"
        payload = decode_access_token(tampered)
        assert payload is None


class TestRBAC:
    def test_employee_can_access_employee(self):
        assert role_has_access("employee", "employee")

    def test_admin_can_access_all(self):
        for role in ["employee", "manager", "hr", "admin"]:
            assert role_has_access("admin", role)

    def test_employee_cannot_access_admin(self):
        assert not role_has_access("employee", "admin")

    def test_hr_can_access_manager(self):
        assert role_has_access("hr", "manager")

    def test_manager_cannot_access_hr(self):
        assert not role_has_access("manager", "hr")

    def test_role_hierarchy_order(self):
        levels = [ROLE_HIERARCHY[r] for r in ["employee", "manager", "hr", "admin"]]
        assert levels == sorted(levels)
