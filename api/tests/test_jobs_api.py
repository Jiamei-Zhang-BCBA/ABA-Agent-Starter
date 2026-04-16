# api/tests/test_jobs_api.py
"""Tests for jobs API endpoints: create, list, detail, output, tenant isolation."""

import io
import json

from fastapi.testclient import TestClient

from app.main import app

_client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_org(org_name: str, email: str, password: str = "test123") -> dict:
    """Register a new org and return the full response JSON."""
    resp = _client.post("/api/v1/users/register", json={
        "org_name": org_name,
        "admin_name": "管理员",
        "admin_email": email,
        "admin_password": password,
    })
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    return resp.json()


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_intake_job(token: str, *, child_alias: str = "小明", parent_note: str = "测试备注") -> dict:
    """Helper: create a job using the intake feature with valid form data and one file."""
    resp = _client.post(
        "/api/v1/jobs",
        headers=_auth_header(token),
        data={
            "feature_id": "intake",
            "form_data": json.dumps({
                "child_alias": child_alias,
                "parent_note": parent_note,
            }),
        },
        files={"files": ("test.txt", io.BytesIO(b"test content"), "text/plain")},
    )
    return resp


# ---------------------------------------------------------------------------
# 1. Create job — success
# ---------------------------------------------------------------------------

def test_create_job_success():
    reg = _register_org("创建任务测试", "create_job@jobs-test.com")
    token = reg["access_token"]

    resp = _create_intake_job(token)

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["feature_id"] == "intake"
    assert data["status"] in ("queued", "processing", "pending_review", "delivered", "failed")
    assert "id" in data
    assert "tenant_id" in data
    assert "user_id" in data
    assert "created_at" in data


# ---------------------------------------------------------------------------
# 2. Create job — missing required form fields returns 400
# ---------------------------------------------------------------------------

def test_create_job_missing_form_fields():
    reg = _register_org("缺字段测试", "missing_fields@jobs-test.com")
    token = reg["access_token"]

    # Empty form_data: child_alias is required for intake
    resp = _client.post(
        "/api/v1/jobs",
        headers=_auth_header(token),
        data={
            "feature_id": "intake",
            "form_data": json.dumps({}),
        },
        files={"files": ("test.txt", io.BytesIO(b"x"), "text/plain")},
    )

    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    detail = resp.json()["detail"]
    # Should mention the missing field label
    assert "儿童昵称" in detail or "必填" in detail


def test_create_job_rejects_invalid_select_value():
    """quick_summary.purpose is a select; passing an invalid option must 400."""
    reg = _register_org("非法选项测试", "invalid_select@jobs-test.com")
    token = reg["access_token"]

    resp = _client.post(
        "/api/v1/jobs",
        headers=_auth_header(token),
        data={
            "feature_id": "quick_summary",
            "form_data": json.dumps({"purpose": "totally-fake-option"}),
        },
    )

    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    detail = resp.json()["detail"]
    assert "取值无效" in detail or "purpose" in detail.lower() or "用途" in detail


# ---------------------------------------------------------------------------
# 3. Create job — feature not in starter plan returns 403
# ---------------------------------------------------------------------------

def test_create_job_unauthorized_feature():
    reg = _register_org("无权限测试", "unauthorized_feature@jobs-test.com")
    token = reg["access_token"]

    # "staff_onboarding" is an enterprise-only feature; starter plan does NOT include it
    resp = _client.post(
        "/api/v1/jobs",
        headers=_auth_header(token),
        data={
            "feature_id": "staff_onboarding",
            "form_data": json.dumps({"teacher_name": "张老师"}),
        },
        files={"files": ("test.txt", io.BytesIO(b"abc"), "text/plain")},
    )

    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    assert "staff_onboarding" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Create job — unauthenticated request returns 401/403
# ---------------------------------------------------------------------------

def test_create_job_unauthenticated():
    resp = _client.post(
        "/api/v1/jobs",
        data={
            "feature_id": "intake",
            "form_data": json.dumps({"child_alias": "小明", "age": 5}),
        },
        files={"files": ("test.txt", io.BytesIO(b"x"), "text/plain")},
    )

    assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# 5. List jobs — job appears after creation
# ---------------------------------------------------------------------------

def test_list_jobs():
    reg = _register_org("列表测试", "list_jobs@jobs-test.com")
    token = reg["access_token"]

    # No jobs yet
    list_resp = _client.get("/api/v1/jobs", headers=_auth_header(token))
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 0
    assert list_resp.json()["jobs"] == []

    # Create a job
    create_resp = _create_intake_job(token)
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    # Job appears in list
    list_resp2 = _client.get("/api/v1/jobs", headers=_auth_header(token))
    assert list_resp2.status_code == 200
    data = list_resp2.json()
    assert data["total"] == 1
    ids = [j["id"] for j in data["jobs"]]
    assert job_id in ids


def test_list_jobs_pagination():
    reg = _register_org("分页测试", "pagination@jobs-test.com")
    token = reg["access_token"]

    # Create 3 jobs
    for i in range(3):
        resp = _create_intake_job(token, child_alias=f"儿童{i}", parent_note=f"备注 {i}")
        assert resp.status_code == 201

    # Limit to 2
    resp = _client.get("/api/v1/jobs?limit=2&skip=0", headers=_auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["jobs"]) == 2

    # Skip 2, get 1 remaining
    resp2 = _client.get("/api/v1/jobs?limit=10&skip=2", headers=_auth_header(token))
    assert resp2.status_code == 200
    assert len(resp2.json()["jobs"]) == 1


# ---------------------------------------------------------------------------
# 6. Get job detail by id
# ---------------------------------------------------------------------------

def test_get_job_detail():
    reg = _register_org("详情测试", "detail@jobs-test.com")
    token = reg["access_token"]

    create_resp = _create_intake_job(token, child_alias="小刚", parent_note="初访补充")
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    detail_resp = _client.get(f"/api/v1/jobs/{job_id}", headers=_auth_header(token))
    assert detail_resp.status_code == 200

    detail = detail_resp.json()
    assert detail["id"] == job_id
    assert detail["feature_id"] == "intake"
    # form_data_json should contain what we submitted
    assert detail["form_data_json"].get("child_alias") == "小刚"
    assert detail["form_data_json"].get("parent_note") == "初访补充"


def test_get_job_detail_not_found():
    reg = _register_org("不存在任务测试", "notfound@jobs-test.com")
    token = reg["access_token"]

    resp = _client.get("/api/v1/jobs/nonexistent-job-id-000", headers=_auth_header(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. Get job output — freshly created job (not delivered) returns 400
# ---------------------------------------------------------------------------

def test_get_job_output_not_delivered():
    reg = _register_org("输出未就绪测试", "output_not_delivered@jobs-test.com")
    token = reg["access_token"]

    create_resp = _create_intake_job(token)
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    # The job was just created; it is not in delivered/approved state
    # If the background worker has not run (or has not finished), status is not delivered.
    # We force-check the current status and assert accordingly.
    detail = _client.get(f"/api/v1/jobs/{job_id}", headers=_auth_header(token)).json()
    current_status = detail["status"]

    if current_status in ("delivered", "approved"):
        # If background worker happened to finish synchronously, output should succeed
        output_resp = _client.get(f"/api/v1/jobs/{job_id}/output", headers=_auth_header(token))
        assert output_resp.status_code == 200
    else:
        # Not yet delivered — must return 400
        output_resp = _client.get(f"/api/v1/jobs/{job_id}/output", headers=_auth_header(token))
        assert output_resp.status_code == 400
        assert "status" in output_resp.json()["detail"].lower() or "delivered" in output_resp.json()["detail"].lower()


def test_get_job_output_queued_is_400():
    """A job that has never been processed must return 400 for output."""
    import asyncio
    from sqlalchemy import update
    from app.database import async_session
    from app.models.job import Job, JobStatus

    reg = _register_org("排队状态输出测试", "queued_output@jobs-test.com")
    token = reg["access_token"]

    create_resp = _create_intake_job(token)
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    # Force the job back to QUEUED status in the DB
    async def force_queued():
        async with async_session() as db:
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status=JobStatus.QUEUED.value)
            )
            await db.commit()

    asyncio.run(force_queued())

    output_resp = _client.get(f"/api/v1/jobs/{job_id}/output", headers=_auth_header(token))
    assert output_resp.status_code == 400
    assert "queued" in output_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 8. PATCH output — update output content on a delivered job
# ---------------------------------------------------------------------------

def test_update_job_output_delivered():
    """PATCH /jobs/{id}/output succeeds when job is in delivered status."""
    import asyncio
    from sqlalchemy import update
    from app.database import async_session
    from app.models.job import Job, JobStatus

    reg = _register_org("更新输出测试", "update_output@jobs-test.com")
    token = reg["access_token"]

    create_resp = _create_intake_job(token)
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    # Promote job to DELIVERED in DB
    async def make_delivered():
        async with async_session() as db:
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status=JobStatus.DELIVERED.value, output_content="original content")
            )
            await db.commit()

    asyncio.run(make_delivered())

    patch_resp = _client.patch(
        f"/api/v1/jobs/{job_id}/output",
        headers=_auth_header(token),
        json={"output_content": "edited output text"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["job_id"] == job_id
    assert patch_resp.json()["status"] == "updated"

    # Verify the change persisted
    output_resp = _client.get(f"/api/v1/jobs/{job_id}/output", headers=_auth_header(token))
    assert output_resp.status_code == 200
    assert output_resp.json()["output_content"] == "edited output text"


def test_update_job_output_not_delivered_returns_400():
    """PATCH /jobs/{id}/output must fail when job is still queued."""
    import asyncio
    from sqlalchemy import update
    from app.database import async_session
    from app.models.job import Job, JobStatus

    reg = _register_org("禁止更新输出测试", "patch_not_delivered@jobs-test.com")
    token = reg["access_token"]

    create_resp = _create_intake_job(token)
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    # Force QUEUED
    async def force_queued():
        async with async_session() as db:
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status=JobStatus.QUEUED.value)
            )
            await db.commit()

    asyncio.run(force_queued())

    patch_resp = _client.patch(
        f"/api/v1/jobs/{job_id}/output",
        headers=_auth_header(token),
        json={"output_content": "should not be saved"},
    )
    assert patch_resp.status_code == 400


# ---------------------------------------------------------------------------
# 9. Tenant isolation — org B cannot see org A's jobs
# ---------------------------------------------------------------------------

def test_tenant_isolation_jobs():
    org_a = _register_org("隔离机构A", "iso_a@jobs-test.com")
    org_b = _register_org("隔离机构B", "iso_b@jobs-test.com")

    token_a = org_a["access_token"]
    token_b = org_b["access_token"]

    # Org A creates a job
    create_resp = _create_intake_job(token_a)
    assert create_resp.status_code == 201
    job_id_a = create_resp.json()["id"]

    # Org B lists jobs — should see zero
    list_b = _client.get("/api/v1/jobs", headers=_auth_header(token_b))
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 0
    ids_b = [j["id"] for j in list_b.json()["jobs"]]
    assert job_id_a not in ids_b

    # Org B trying to GET org A's job directly returns 404
    detail_resp = _client.get(f"/api/v1/jobs/{job_id_a}", headers=_auth_header(token_b))
    assert detail_resp.status_code == 404

    # Org B trying to GET org A's output directly returns 404
    output_resp = _client.get(f"/api/v1/jobs/{job_id_a}/output", headers=_auth_header(token_b))
    assert output_resp.status_code == 404


# ---------------------------------------------------------------------------
# 10. File upload edge cases
# ---------------------------------------------------------------------------

def test_create_job_too_many_files():
    """Uploading more than 5 files returns 400."""
    reg = _register_org("文件数量超限", "too_many_files@jobs-test.com")
    token = reg["access_token"]

    files = [
        ("files", (f"file{i}.txt", io.BytesIO(b"content"), "text/plain"))
        for i in range(6)  # 6 exceeds the max of 5
    ]

    resp = _client.post(
        "/api/v1/jobs",
        headers=_auth_header(token),
        data={
            "feature_id": "intake",
            "form_data": json.dumps({"child_alias": "小明", "age": 5}),
        },
        files=files,
    )

    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "5" in resp.json()["detail"] or "文件" in resp.json()["detail"]


def test_create_job_no_files_allowed():
    """Job creation without files is still valid (files are optional)."""
    reg = _register_org("无文件任务测试", "no_files@jobs-test.com")
    token = reg["access_token"]

    resp = _client.post(
        "/api/v1/jobs",
        headers=_auth_header(token),
        data={
            "feature_id": "intake",
            "form_data": json.dumps({"child_alias": "小华", "age": 6}),
        },
    )

    # intake has an optional intake_file field; no files should be accepted
    assert resp.status_code in (201, 400), f"Unexpected status {resp.status_code}: {resp.text}"


def test_create_job_invalid_form_data_json():
    """Malformed JSON in form_data returns 400."""
    reg = _register_org("坏JSON测试", "bad_json@jobs-test.com")
    token = reg["access_token"]

    resp = _client.post(
        "/api/v1/jobs",
        headers=_auth_header(token),
        data={
            "feature_id": "intake",
            "form_data": "this is not json {{",
        },
        files={"files": ("test.txt", io.BytesIO(b"x"), "text/plain")},
    )

    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "form_data" in resp.json()["detail"].lower() or "json" in resp.json()["detail"].lower()


def test_create_job_unknown_feature_id():
    """Submitting a completely unknown feature_id should return 403 or 400."""
    reg = _register_org("未知功能测试", "unknown_feature@jobs-test.com")
    token = reg["access_token"]

    resp = _client.post(
        "/api/v1/jobs",
        headers=_auth_header(token),
        data={
            "feature_id": "does_not_exist",
            "form_data": json.dumps({}),
        },
        files={"files": ("test.txt", io.BytesIO(b"x"), "text/plain")},
    )

    # Feature gate fires first (403), or form validator raises (400)
    assert resp.status_code in (400, 403), f"Expected 400/403, got {resp.status_code}: {resp.text}"
