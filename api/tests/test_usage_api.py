# api/tests/test_usage_api.py
"""Tests for usage API endpoints."""

from fastapi.testclient import TestClient

from app.main import app

_client = TestClient(app)


def _register_and_get_token(email: str) -> str:
    resp = _client.post("/api/v1/users/register", json={
        "org_name": f"Usage-{email}",
        "admin_name": "管理员",
        "admin_email": email,
        "admin_password": "test123",
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_monthly_usage_requires_auth():
    res = _client.get("/api/v1/usage/monthly")
    assert res.status_code in (401, 403)


def test_monthly_usage_returns_data():
    token = _register_and_get_token("monthly_usage@test.com")
    res = _client.get("/api/v1/usage/monthly?year_month=2026-04", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert "total_jobs" in data
    assert "total_input_tokens" in data
    assert "total_cost_cents" in data


def test_daily_usage_returns_list():
    token = _register_and_get_token("daily_usage@test.com")
    res = _client.get("/api/v1/usage/daily?year_month=2026-04", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert "breakdown" in data
    assert isinstance(data["breakdown"], list)


def test_monthly_usage_defaults_to_current_month():
    token = _register_and_get_token("default_month@test.com")
    res = _client.get("/api/v1/usage/monthly", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert "year_month" in data
