"""
Tests for the super-admin cancel_job endpoint.

Created after BUG #17 (retry-after-timeout fix) to clean up zombie jobs.

Endpoint: POST /api/v1/jobs/{job_id}/admin-cancel
  - Requires user.email in SUPER_ADMIN_EMAILS
  - Only works on non-terminal statuses (queued/parsing/processing)
  - Marks job as FAILED with a traceable error_message
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.database import async_session
from app.models.job import Job, JobStatus
from app.models.tenant import Tenant, Plan
from app.models.user import User, UserRole
from app.services.auth_service import hash_password


_client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _add_super_admin_email(email: str):
    """Append email to SUPER_ADMIN_EMAILS at runtime."""
    from app.config import get_settings
    settings = get_settings()
    if email not in settings.super_admin_emails:
        settings.super_admin_emails = [*settings.super_admin_emails, email]


async def _make_tenant() -> Tenant:
    async with async_session() as db:
        plan = (await db.execute(select(Plan).limit(1))).scalar_one_or_none()
        tenant = Tenant(
            name=f"Org-{uuid.uuid4().hex[:6]}",
            plan_id=plan.id,
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


async def _make_user(tenant_id, email, role=UserRole.ORG_ADMIN.value) -> User:
    async with async_session() as db:
        u = User(
            email=email,
            password_hash=hash_password("TestPass123!"),
            name=f"User-{email[:6]}",
            role=role,
            tenant_id=tenant_id,
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)
        return u


async def _make_job(tenant_id, user_id, status: str) -> Job:
    async with async_session() as db:
        j = Job(
            tenant_id=tenant_id,
            user_id=user_id,
            feature_id="privacy_filter",
            status=status,
            form_data_json={},
        )
        db.add(j)
        await db.commit()
        await db.refresh(j)
        return j


def _login(email, password="TestPass123!") -> str:
    resp = _client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_super_admin_can_cancel_queued_job():
    email = f"super-q-{uuid.uuid4().hex[:6]}@example.com"
    _add_super_admin_email(email)

    t = asyncio.run(_make_tenant())
    u = asyncio.run(_make_user(t.id, email))
    j = asyncio.run(_make_job(t.id, u.id, JobStatus.QUEUED.value))

    token = _login(email)
    resp = _client.post(
        f"/api/v1/jobs/{j.id}/admin-cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job_id"] == j.id
    assert body["previous_status"] == "queued"
    assert body["new_status"] == "failed"
    assert body["cancelled_by"] == email


def test_non_super_admin_is_rejected():
    super_email = f"super-r-{uuid.uuid4().hex[:6]}@example.com"
    regular_email = f"regular-{uuid.uuid4().hex[:6]}@example.com"
    _add_super_admin_email(super_email)

    t = asyncio.run(_make_tenant())
    super_u = asyncio.run(_make_user(t.id, super_email))
    asyncio.run(_make_user(t.id, regular_email, role=UserRole.BCBA.value))
    j = asyncio.run(_make_job(t.id, super_u.id, JobStatus.QUEUED.value))

    token = _login(regular_email)
    resp = _client.post(
        f"/api/v1/jobs/{j.id}/admin-cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, resp.text


def test_cannot_cancel_terminal_job():
    email = f"super-t-{uuid.uuid4().hex[:6]}@example.com"
    _add_super_admin_email(email)

    t = asyncio.run(_make_tenant())
    u = asyncio.run(_make_user(t.id, email))
    j = asyncio.run(_make_job(t.id, u.id, JobStatus.DELIVERED.value))

    token = _login(email)
    resp = _client.post(
        f"/api/v1/jobs/{j.id}/admin-cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    assert "terminal state" in resp.json()["detail"]


def test_cancel_nonexistent_job_returns_404():
    email = f"super-n-{uuid.uuid4().hex[:6]}@example.com"
    _add_super_admin_email(email)

    t = asyncio.run(_make_tenant())
    asyncio.run(_make_user(t.id, email))

    token = _login(email)
    resp = _client.post(
        "/api/v1/jobs/nonexistent-uuid-12345/admin-cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_cancel_processing_job_allowed():
    email = f"super-p-{uuid.uuid4().hex[:6]}@example.com"
    _add_super_admin_email(email)

    t = asyncio.run(_make_tenant())
    u = asyncio.run(_make_user(t.id, email))
    j = asyncio.run(_make_job(t.id, u.id, JobStatus.PROCESSING.value))

    token = _login(email)
    resp = _client.post(
        f"/api/v1/jobs/{j.id}/admin-cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["previous_status"] == "processing"
    assert resp.json()["new_status"] == "failed"
