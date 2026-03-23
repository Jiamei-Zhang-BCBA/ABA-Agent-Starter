# api/tests/test_review_flow.py
"""
Tests for the ABA SaaS review workflow HTTP endpoints.

Covers:
- GET  /api/v1/reviews            — list pending reviews (org_admin / bcba only)
- POST /api/v1/reviews/{id}/approve — approve with optional modifications
- POST /api/v1/reviews/{id}/reject  — reject with required comments

TDD cycle: tests written before implementation is verified; each test
drives one clearly-stated behavioural expectation.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.database import async_session
from app.main import app
from app.models.job import Job, JobStatus
from app.models.review import Review, ReviewStatus

_client = TestClient(app)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _register_org(
    org_name: str = "审核机构",
    admin_name: str = "管理员",
    email: str = "reviewadmin@test.com",
    password: str = "test123",
):
    """Register a new organisation and return the full response JSON."""
    resp = _client.post("/api/v1/users/register", json={
        "org_name": org_name,
        "admin_name": admin_name,
        "admin_email": email,
        "admin_password": password,
    })
    return resp


def _login(email: str, password: str) -> str:
    resp = _client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json().get("access_token")


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _invite_and_accept(admin_token: str, email: str, role: str, name: str, password: str = "test123"):
    """Invite a user and immediately accept the invitation."""
    invite = _client.post(
        "/api/v1/users/invite",
        json={"email": email, "role": role},
        headers=_auth_header(admin_token),
    ).json()
    accept = _client.post("/api/v1/users/invite/accept", json={
        "token": invite["token"],
        "name": name,
        "password": password,
    }).json()
    return accept


async def _create_test_job_and_review(tenant_id: str, user_id: str):
    """
    Insert a Job (status=pending_review) and a linked pending Review directly
    into the database, bypassing the job processor that requires Claude.

    Returns (job_id, review_id).
    """
    async with async_session() as db:
        job = Job(
            tenant_id=tenant_id,
            user_id=user_id,
            feature_id="intake",
            status=JobStatus.PENDING_REVIEW.value,
        )
        db.add(job)
        await db.flush()

        review = Review(
            job_id=job.id,
            output_content="测试输出内容",
            status=ReviewStatus.PENDING.value,
        )
        db.add(review)
        await db.commit()
        await db.refresh(job)
        await db.refresh(review)
        return job.id, review.id


async def _get_job_status(job_id: str) -> str:
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one()
        return job.status


async def _get_review(review_id: str) -> Review:
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(select(Review).where(Review.id == review_id))
        return result.scalar_one()


# ---------------------------------------------------------------------------
# 1. test_list_reviews_empty
# ---------------------------------------------------------------------------

def test_list_reviews_empty():
    """A freshly registered org has no pending reviews."""
    reg = _register_org(
        email="listreview@test.com",
        org_name="列表审核测试",
    ).json()
    token = reg["access_token"]

    resp = _client.get("/api/v1/reviews", headers=_auth_header(token))

    assert resp.status_code == 200
    data = resp.json()
    assert "reviews" in data
    assert data["reviews"] == []


# ---------------------------------------------------------------------------
# 2. test_approve_review_flow
# ---------------------------------------------------------------------------

def test_approve_review_flow():
    """Approving a review marks the review as approved and sets the job to delivered."""
    reg = _register_org(
        email="approveflow@test.com",
        org_name="批准流程测试",
    ).json()
    tenant_id = reg["tenant_id"]
    user_id = reg["user_id"]
    token = reg["access_token"]

    job_id, review_id = asyncio.run(_create_test_job_and_review(tenant_id, user_id))

    resp = _client.post(
        f"/api/v1/reviews/{review_id}/approve",
        json={},
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == review_id
    assert data["status"] == ReviewStatus.APPROVED.value
    assert data["reviewed_at"] is not None

    job_status = asyncio.run(_get_job_status(job_id))
    assert job_status == JobStatus.DELIVERED.value


# ---------------------------------------------------------------------------
# 3. test_reject_review_flow
# ---------------------------------------------------------------------------

def test_reject_review_flow():
    """Rejecting a review marks the review as rejected and sets the job to rejected."""
    reg = _register_org(
        email="rejectflow@test.com",
        org_name="拒绝流程测试",
    ).json()
    tenant_id = reg["tenant_id"]
    user_id = reg["user_id"]
    token = reg["access_token"]

    job_id, review_id = asyncio.run(_create_test_job_and_review(tenant_id, user_id))

    resp = _client.post(
        f"/api/v1/reviews/{review_id}/reject",
        json={"comments": "内容不符合规范，请修改后重新提交。"},
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == review_id
    assert data["status"] == ReviewStatus.REJECTED.value
    assert data["comments"] == "内容不符合规范，请修改后重新提交。"
    assert data["reviewed_at"] is not None

    job_status = asyncio.run(_get_job_status(job_id))
    assert job_status == JobStatus.REJECTED.value


# ---------------------------------------------------------------------------
# 4. test_approve_with_modified_content
# ---------------------------------------------------------------------------

def test_approve_with_modified_content():
    """
    Approving with modified_content stores the modification on the review
    and propagates it as the job's output_content.
    """
    reg = _register_org(
        email="modifyapprove@test.com",
        org_name="修改审核测试",
    ).json()
    tenant_id = reg["tenant_id"]
    user_id = reg["user_id"]
    token = reg["access_token"]

    job_id, review_id = asyncio.run(_create_test_job_and_review(tenant_id, user_id))

    modified = "已由督导修改：更新了目标行为定义与干预策略。"
    resp = _client.post(
        f"/api/v1/reviews/{review_id}/approve",
        json={"modified_content": modified, "comments": "小幅修改后批准"},
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == ReviewStatus.APPROVED.value
    assert data["modified_content"] == modified
    assert data["comments"] == "小幅修改后批准"

    # The job's output_content should reflect the modified version
    async def _get_job_output(job_id: str) -> str:
        async with async_session() as db:
            from sqlalchemy import select
            result = await db.execute(select(Job).where(Job.id == job_id))
            return result.scalar_one().output_content

    job_output = asyncio.run(_get_job_output(job_id))
    assert job_output == modified


# ---------------------------------------------------------------------------
# 5. test_teacher_cannot_access_reviews
# ---------------------------------------------------------------------------

def test_teacher_cannot_access_reviews():
    """A user with the 'teacher' role receives 403 when listing reviews."""
    reg = _register_org(
        email="teacherreview@test.com",
        org_name="教师权限审核测试",
    ).json()
    admin_token = reg["access_token"]

    _invite_and_accept(
        admin_token=admin_token,
        email="classteacher@test.com",
        role="teacher",
        name="普通老师",
    )
    teacher_token = _login("classteacher@test.com", "test123")

    resp = _client.get("/api/v1/reviews", headers=_auth_header(teacher_token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 6. test_approve_nonexistent_review
# ---------------------------------------------------------------------------

def test_approve_nonexistent_review():
    """Attempting to approve a review that does not exist returns 404."""
    reg = _register_org(
        email="notfoundreview@test.com",
        org_name="不存在审核测试",
    ).json()
    token = reg["access_token"]

    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = _client.post(
        f"/api/v1/reviews/{fake_id}/approve",
        json={},
        headers=_auth_header(token),
    )

    assert resp.status_code == 404
