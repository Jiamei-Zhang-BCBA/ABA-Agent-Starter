# api/tests/test_dashboard.py
"""Tests for dashboard overview endpoint."""

from fastapi.testclient import TestClient

from app.main import app

_client = TestClient(app)


def _register_and_get_token(email: str) -> str:
    resp = _client.post("/api/v1/users/register", json={
        "org_name": f"Dash-{email}",
        "admin_name": "管理员",
        "admin_email": email,
        "admin_password": "test123",
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_requires_auth():
    res = _client.get("/api/v1/dashboard/overview")
    assert res.status_code in (401, 403)


def test_dashboard_returns_overview():
    token = _register_and_get_token("dashboard@test.com")
    res = _client.get("/api/v1/dashboard/overview", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert "total_clients" in data
    assert "total_jobs_this_month" in data
    assert "completion_rate" in data
    assert "token_usage" in data
    assert "recent_jobs" in data
    assert "pending_reviews" in data
