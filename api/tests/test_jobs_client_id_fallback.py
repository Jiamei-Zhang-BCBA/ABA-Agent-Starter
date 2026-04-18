# api/tests/test_jobs_client_id_fallback.py
"""
BUG #18 regression tests:
- POST /api/v1/jobs must persist Job.client_id even when the API caller put
  `client_id` only inside the form_data JSON (not as a top-level multipart
  Form field). Without the fix, review_service.approve_review silently
  skipped vault writes because client_code could not be resolved.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

_client = TestClient(app)


def _register(email: str, password: str = "test123") -> dict:
    resp = _client.post("/api/v1/users/register", json={
        "org_name": "bug18-" + email.split("@")[0],
        "admin_name": "管理员",
        "admin_email": email,
        "admin_password": password,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_client(token: str, code_name: str, alias: str) -> str:
    resp = _client.post(
        "/api/v1/clients",
        headers=_auth(token),
        json={"code_name": code_name, "display_alias": alias},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# Prevent the test from actually invoking Claude CLI — we only care about the
# Job.client_id persistence check.
def _mock_dispatch(job_id: str) -> None:  # noqa: ARG001
    return None


# ---------------------------------------------------------------------------
# 1. Top-level client_id only → persisted (pre-existing behaviour stays green)
# ---------------------------------------------------------------------------


def _assessment_payload(cid: str, include_top_level: bool) -> dict:
    data = {
        "feature_id": "assessment",
        "form_data": json.dumps({
            "client_id": cid,
            "tool_name": "VB-MAPP",
        }),
    }
    if include_top_level:
        data["client_id"] = cid
    return data


def _assessment_files() -> dict:
    return {
        "files": (
            "vbmapp.md",
            io.BytesIO("# 基线评估\n测试内容".encode("utf-8")),
            "text/markdown",
        ),
    }


def test_bug18_top_level_client_id_is_persisted():
    reg = _register("bug18_top@example.com")
    token = reg["access_token"]
    cid = _create_client(token, "A-bug18-top", "测试童A")

    with patch("app.routers.jobs._dispatch_job", _mock_dispatch):
        resp = _client.post(
            "/api/v1/jobs",
            headers=_auth(token),
            data=_assessment_payload(cid, include_top_level=True),
            files=_assessment_files(),
        )

    assert resp.status_code == 201, resp.text
    assert resp.json()["client_id"] == cid


# ---------------------------------------------------------------------------
# 2. BUG #18 fix: client_id only in form_data → should still be persisted
# ---------------------------------------------------------------------------


def test_bug18_form_data_only_client_id_gets_backfilled():
    reg = _register("bug18_form_only@example.com")
    token = reg["access_token"]
    cid = _create_client(token, "A-bug18-form", "测试童B")

    with patch("app.routers.jobs._dispatch_job", _mock_dispatch):
        resp = _client.post(
            "/api/v1/jobs",
            headers=_auth(token),
            data=_assessment_payload(cid, include_top_level=False),
            files=_assessment_files(),
        )

    assert resp.status_code == 201, resp.text
    # BUG #18 guard: without the fix this used to be None
    assert resp.json()["client_id"] == cid, (
        "BUG #18 regression: Job.client_id was not backfilled from form_data"
    )


# ---------------------------------------------------------------------------
# 3. Neither source sets client_id → stays None (client-optional skills)
# ---------------------------------------------------------------------------


def test_bug18_no_client_id_anywhere_stays_none():
    """intake bootstraps a new case, so it never carries a client_id upfront."""
    reg = _register("bug18_none@example.com")
    token = reg["access_token"]

    with patch("app.routers.jobs._dispatch_job", _mock_dispatch):
        resp = _client.post(
            "/api/v1/jobs",
            headers=_auth(token),
            data={
                "feature_id": "intake",
                "form_data": json.dumps({
                    "child_alias": "测试童C",
                }),
            },
            files={
                "files": (
                    "intake.md",
                    io.BytesIO("# 初访笔录\n内容".encode("utf-8")),
                    "text/markdown",
                ),
            },
        )

    assert resp.status_code == 201, resp.text
    assert resp.json()["client_id"] is None


# ---------------------------------------------------------------------------
# 4. form_data.client_id for client the user has no access to → still 403
#    (regression guard: backfill MUST go through _check_client_access)
# ---------------------------------------------------------------------------


def test_bug18_backfilled_client_id_still_enforces_access_check():
    # Owner A creates their own client
    reg_a = _register("bug18_owner@example.com")
    token_a = reg_a["access_token"]
    foreign_cid = _create_client(token_a, "A-bug18-foreign", "别家孩子")

    # Owner B tries to submit a job naming that other tenant's client
    reg_b = _register("bug18_intruder@example.com")
    token_b = reg_b["access_token"]

    with patch("app.routers.jobs._dispatch_job", _mock_dispatch):
        resp = _client.post(
            "/api/v1/jobs",
            headers=_auth(token_b),
            data={
                "feature_id": "assessment",
                # No top-level client_id, but smuggle foreign cid via form_data
                "form_data": json.dumps({
                    "client_id": foreign_cid,
                    "tool_name": "VB-MAPP",
                }),
            },
            files=_assessment_files(),
        )

    # Must be blocked — the fallback path still runs _check_client_access
    assert resp.status_code in (403, 404), (
        "Backfilled client_id must still pass tenant isolation check. "
        f"Got {resp.status_code}: {resp.text}"
    )
