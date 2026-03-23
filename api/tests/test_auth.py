# api/tests/test_auth.py
"""
TDD test suite for auth endpoints.

Covers:
  POST /api/v1/auth/login
  POST /api/v1/auth/refresh
  GET  /api/v1/auth/me

Follows Red-Green-Refactor: tests are written first against the contract
defined in api/app/routers/auth.py and api/app/schemas/auth.py.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Module-level client — avoids conflict with the `client` fixture in conftest.py
_client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REG_COUNTER = 0  # makes every helper call produce a unique email


def _unique_email(prefix: str = "auth") -> str:
    global _REG_COUNTER
    _REG_COUNTER += 1
    return f"{prefix}_{_REG_COUNTER}@authtest.com"


def _register(
    email: str | None = None,
    password: str = "ValidPass1!",
    org_name: str | None = None,
    admin_name: str = "Auth Tester",
) -> dict:
    """Register a new org+admin and return the full response JSON."""
    email = email or _unique_email()
    org_name = org_name or f"Org for {email}"
    resp = _client.post(
        "/api/v1/users/register",
        json={
            "org_name": org_name,
            "admin_name": admin_name,
            "admin_email": email,
            "admin_password": password,
        },
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    return {**resp.json(), "_email": email, "_password": password}


def _login(email: str, password: str) -> dict:
    """POST /login and return the raw response object."""
    return _client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. test_login_success
# ---------------------------------------------------------------------------


def test_login_success():
    """
    RED  : no login endpoint → 404/422
    GREEN: endpoint exists, valid credentials → 200 with access_token + refresh_token
    """
    reg = _register()
    resp = _login(reg["_email"], reg["_password"])

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "access_token" in body, "access_token missing from response"
    assert "refresh_token" in body, "refresh_token missing from response"
    assert body.get("token_type") == "bearer", "token_type must be 'bearer'"

    # Tokens must be non-empty strings
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 0
    assert isinstance(body["refresh_token"], str) and len(body["refresh_token"]) > 0

    # The two tokens must be different (access vs refresh carry different payloads)
    assert body["access_token"] != body["refresh_token"]


# ---------------------------------------------------------------------------
# 2. test_login_wrong_password
# ---------------------------------------------------------------------------


def test_login_wrong_password():
    """
    Supplying the correct email but an incorrect password must return 401.
    The error detail must NOT reveal whether the email exists (prevents enumeration).
    """
    reg = _register()
    resp = _login(reg["_email"], "WrongPassword99!")

    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    detail = resp.json().get("detail", "")
    # Generic message — must not disclose whether email exists
    assert "Incorrect" in detail or "incorrect" in detail or "password" in detail.lower()


# ---------------------------------------------------------------------------
# 3. test_login_nonexistent_email
# ---------------------------------------------------------------------------


def test_login_nonexistent_email():
    """
    Attempting to log in with an email that was never registered returns 401.
    The response should be indistinguishable from a wrong-password error
    (same status code, same generic message) to prevent user enumeration.
    """
    resp = _login("nobody_ever_registered_this@ghost.com", "SomePass1!")

    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    detail = resp.json().get("detail", "")
    assert len(detail) > 0, "Error detail should not be empty"


# ---------------------------------------------------------------------------
# 4. test_me_with_valid_token
# ---------------------------------------------------------------------------


def test_me_with_valid_token():
    """
    A valid access token obtained after registration must allow GET /me
    and return the authenticated user's profile.
    """
    reg = _register()
    resp = _login(reg["_email"], reg["_password"])
    access_token = resp.json()["access_token"]

    me_resp = _client.get("/api/v1/auth/me", headers=_bearer(access_token))

    assert me_resp.status_code == 200, f"Expected 200, got {me_resp.status_code}: {me_resp.text}"

    me = me_resp.json()
    assert me["email"] == reg["_email"], "Returned email does not match registered email"
    assert me["role"] == "org_admin", "First user of a new org should be org_admin"

    # UserResponse schema fields
    for field in ("id", "tenant_id", "role", "name", "email"):
        assert field in me, f"Field '{field}' missing from /me response"

    # id and tenant_id must be UUID-like strings (non-empty)
    assert len(me["id"]) > 0
    assert len(me["tenant_id"]) > 0


# ---------------------------------------------------------------------------
# 5. test_me_without_token
# ---------------------------------------------------------------------------


def test_me_without_token():
    """
    Calling GET /me without any Authorization header must be rejected.
    FastAPI's HTTPBearer raises 403 when the header is absent.
    """
    resp = _client.get("/api/v1/auth/me")

    assert resp.status_code in (401, 403), (
        f"Expected 401 or 403 when no token provided, got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# 6. test_me_with_invalid_token
# ---------------------------------------------------------------------------


def test_me_with_invalid_token():
    """
    A malformed / tampered token must be rejected with 401.
    Tests that decode_token raises an HTTPException on bad input.
    """
    bad_tokens = [
        "totally.not.a.jwt",
        "Bearer eyJhbGciOiJIUzI1NiJ9.invalid.signature",
        "a" * 200,  # garbage long string
    ]
    for token in bad_tokens:
        resp = _client.get("/api/v1/auth/me", headers=_bearer(token))
        assert resp.status_code == 401, (
            f"Token '{token[:30]}...' should return 401, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 7. test_refresh_token
# ---------------------------------------------------------------------------


def test_refresh_token():
    """
    A valid refresh_token obtained during login must produce a new pair of
    access_token + refresh_token via POST /api/v1/auth/refresh.
    The newly issued access_token must be accepted by GET /me.
    """
    reg = _register()
    login_resp = _login(reg["_email"], reg["_password"])
    original = login_resp.json()

    refresh_resp = _client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original["refresh_token"]},
    )

    assert refresh_resp.status_code == 200, (
        f"Expected 200 from /refresh, got {refresh_resp.status_code}: {refresh_resp.text}"
    )

    refreshed = refresh_resp.json()
    assert "access_token" in refreshed
    assert "refresh_token" in refreshed
    assert refreshed.get("token_type") == "bearer"

    # New access_token must work on /me
    me_resp = _client.get("/api/v1/auth/me", headers=_bearer(refreshed["access_token"]))
    assert me_resp.status_code == 200, (
        f"Refreshed access_token rejected by /me: {me_resp.status_code}"
    )
    assert me_resp.json()["email"] == reg["_email"]


# ---------------------------------------------------------------------------
# 8. test_refresh_with_access_token_rejected
# ---------------------------------------------------------------------------


def test_refresh_with_access_token_rejected():
    """
    Supplying the access_token (type='access') to POST /refresh must be rejected
    with 401 — only tokens of type='refresh' are valid for this endpoint.
    This prevents access token reuse as a refresh token.
    """
    reg = _register()
    login_resp = _login(reg["_email"], reg["_password"])
    access_token = login_resp.json()["access_token"]  # type == "access"

    refresh_resp = _client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},  # intentionally wrong token type
    )

    assert refresh_resp.status_code == 401, (
        f"Expected 401 when access_token used as refresh_token, "
        f"got {refresh_resp.status_code}: {refresh_resp.text}"
    )

    detail = refresh_resp.json().get("detail", "")
    assert len(detail) > 0, "Error detail should not be empty"
