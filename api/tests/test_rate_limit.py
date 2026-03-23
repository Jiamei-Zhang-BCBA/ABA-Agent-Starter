# api/tests/test_rate_limit.py
from fastapi.testclient import TestClient
from app.main import app

_client = TestClient(app)


def test_login_rate_limited_after_5_attempts():
    """POST /auth/login should be limited to 5/minute per IP."""
    for i in range(5):
        _client.post("/api/v1/auth/login", json={"email": "bad@x.com", "password": "wrong"})

    resp = _client.post("/api/v1/auth/login", json={"email": "bad@x.com", "password": "wrong"})
    assert resp.status_code == 429
    assert "rate" in resp.json().get("detail", "").lower() or resp.status_code == 429
