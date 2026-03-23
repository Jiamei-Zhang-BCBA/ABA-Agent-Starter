# api/tests/test_user_management.py
"""Tests for Sprint 2: User registration, invitation, CRUD, password reset."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

_client = TestClient(app)


# --- Helpers ---

def _register_org(org_name="测试机构", admin_name="管理员", email="admin@test.com", password="test123"):
    return _client.post("/api/v1/users/register", json={
        "org_name": org_name,
        "admin_name": admin_name,
        "admin_email": email,
        "admin_password": password,
    })


def _login(email, password):
    resp = _client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json().get("access_token")


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# --- Registration ---

def test_register_creates_tenant_and_admin():
    resp = _register_org()
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "admin@test.com"
    assert "access_token" in data
    assert "tenant_id" in data


def test_register_duplicate_email_rejected():
    _register_org(email="dup@test.com")
    resp = _register_org(email="dup@test.com", org_name="另一机构")
    assert resp.status_code == 400
    assert "已被注册" in resp.json()["detail"]


def test_registered_admin_can_login():
    _register_org(email="login@test.com", org_name="登录测试")
    token = _login("login@test.com", "test123")
    assert token is not None

    resp = _client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "org_admin"


# --- Invitation Flow ---

def test_invite_accept_login_flow():
    # Register org
    reg = _register_org(email="boss@invite.com", org_name="邀请测试").json()
    token = reg["access_token"]

    # Invite a teacher
    invite_resp = _client.post(
        "/api/v1/users/invite",
        json={"email": "teacher@invite.com", "role": "teacher"},
        headers=_auth_header(token),
    )
    assert invite_resp.status_code == 201
    invite_token = invite_resp.json()["token"]

    # Accept invitation
    accept_resp = _client.post("/api/v1/users/invite/accept", json={
        "token": invite_token,
        "name": "小李老师",
        "password": "teach123",
    })
    assert accept_resp.status_code == 201
    assert accept_resp.json()["email"] == "teacher@invite.com"

    # Teacher can login
    teacher_token = _login("teacher@invite.com", "teach123")
    me = _client.get("/api/v1/auth/me", headers=_auth_header(teacher_token)).json()
    assert me["role"] == "teacher"


def test_invite_org_admin_rejected():
    reg = _register_org(email="noadmin@test.com", org_name="拒绝邀请管理员").json()
    resp = _client.post(
        "/api/v1/users/invite",
        json={"email": "x@test.com", "role": "org_admin"},
        headers=_auth_header(reg["access_token"]),
    )
    assert resp.status_code == 422  # pydantic validation rejects org_admin


def test_invite_expired_token_rejected():
    reg = _register_org(email="expire@test.com", org_name="过期测试").json()
    token = reg["access_token"]

    invite_resp = _client.post(
        "/api/v1/users/invite",
        json={"email": "expired@test.com", "role": "bcba"},
        headers=_auth_header(token),
    )
    invite_token = invite_resp.json()["token"]

    # Manually expire the token in DB
    from app.database import async_session
    from app.models.invitation import Invitation
    from sqlalchemy import update
    from datetime import datetime
    import asyncio

    async def expire_token():
        async with async_session() as db:
            await db.execute(
                update(Invitation)
                .where(Invitation.token == invite_token)
                .values(expires_at=datetime(2020, 1, 1))
            )
            await db.commit()

    asyncio.run(expire_token())

    resp = _client.post("/api/v1/users/invite/accept", json={
        "token": invite_token,
        "name": "过期用户",
        "password": "test123",
    })
    assert resp.status_code == 400
    assert "过期" in resp.json()["detail"]


# --- User CRUD ---

def test_list_users():
    reg = _register_org(email="list@test.com", org_name="列表测试").json()
    token = reg["access_token"]

    resp = _client.get("/api/v1/users", headers=_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
    assert any(u["email"] == "list@test.com" for u in resp.json()["users"])


def test_update_user_role():
    reg = _register_org(email="crud@test.com", org_name="CRUD测试").json()
    token = reg["access_token"]

    # Invite and accept a bcba
    invite = _client.post(
        "/api/v1/users/invite",
        json={"email": "bcba@crud.com", "role": "bcba"},
        headers=_auth_header(token),
    ).json()
    accept = _client.post("/api/v1/users/invite/accept", json={
        "token": invite["token"], "name": "张督导", "password": "test123",
    }).json()

    # Update role to teacher
    resp = _client.patch(
        f"/api/v1/users/{accept['user_id']}",
        json={"role": "teacher"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "teacher"


def test_delete_user_soft_deletes():
    reg = _register_org(email="del@test.com", org_name="删除测试").json()
    token = reg["access_token"]

    invite = _client.post(
        "/api/v1/users/invite",
        json={"email": "todel@test.com", "role": "teacher"},
        headers=_auth_header(token),
    ).json()
    accept = _client.post("/api/v1/users/invite/accept", json={
        "token": invite["token"], "name": "待删除", "password": "test123",
    }).json()

    resp = _client.delete(
        f"/api/v1/users/{accept['user_id']}",
        headers=_auth_header(token),
    )
    assert resp.status_code == 204

    # Verify user is inactive
    detail = _client.get(
        f"/api/v1/users/{accept['user_id']}",
        headers=_auth_header(token),
    )
    assert detail.json()["is_active"] is False


def test_cannot_delete_self():
    reg = _register_org(email="selfdelete@test.com", org_name="自删测试").json()
    resp = _client.delete(
        f"/api/v1/users/{reg['user_id']}",
        headers=_auth_header(reg["access_token"]),
    )
    assert resp.status_code == 400
    assert "自己" in resp.json()["detail"]


# --- Tenant Isolation ---

def test_tenant_isolation():
    # Register two separate orgs
    org_a = _register_org(email="a@iso.com", org_name="机构A").json()
    org_b = _register_org(email="b@iso.com", org_name="机构B").json()

    # Org A lists users — should not see Org B's admin
    users_a = _client.get("/api/v1/users", headers=_auth_header(org_a["access_token"])).json()
    emails = [u["email"] for u in users_a["users"]]
    assert "a@iso.com" in emails
    assert "b@iso.com" not in emails


# --- Password Reset ---

def test_password_reset_flow():
    _register_org(email="reset@test.com", org_name="重置测试")

    # Request reset
    resp = _client.post("/api/v1/users/password-reset", json={"email": "reset@test.com"})
    assert resp.status_code == 200

    # Get the token from DB
    from app.database import async_session
    from app.models.password_reset import PasswordResetToken
    from sqlalchemy import select
    import asyncio

    async def get_token():
        async with async_session() as db:
            result = await db.execute(
                select(PasswordResetToken).order_by(PasswordResetToken.created_at.desc())
            )
            return result.scalar_one().token

    reset_token = asyncio.run(get_token())

    # Confirm reset
    resp = _client.post("/api/v1/users/password-reset/confirm", json={
        "token": reset_token,
        "new_password": "newpass123",
    })
    assert resp.status_code == 200

    # Login with new password
    login_token = _login("reset@test.com", "newpass123")
    assert login_token is not None

    # Old password no longer works
    old_resp = _client.post("/api/v1/auth/login", json={
        "email": "reset@test.com", "password": "test123",
    })
    assert old_resp.status_code == 401


def test_password_reset_nonexistent_email_still_200():
    resp = _client.post("/api/v1/users/password-reset", json={"email": "nobody@test.com"})
    assert resp.status_code == 200  # Prevent email enumeration


# --- Permission Boundary ---

def test_teacher_cannot_list_users():
    reg = _register_org(email="perm@test.com", org_name="权限测试").json()
    token = reg["access_token"]

    # Create a teacher
    invite = _client.post(
        "/api/v1/users/invite",
        json={"email": "teacherperm@test.com", "role": "teacher"},
        headers=_auth_header(token),
    ).json()
    accept = _client.post("/api/v1/users/invite/accept", json={
        "token": invite["token"], "name": "权限老师", "password": "test123",
    }).json()

    teacher_token = _login("teacherperm@test.com", "test123")

    # Teacher cannot list users
    resp = _client.get("/api/v1/users", headers=_auth_header(teacher_token))
    assert resp.status_code == 403
