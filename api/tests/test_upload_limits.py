# api/tests/test_upload_limits.py
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _login_token():
    resp = client.post("/api/v1/auth/login", json={"email": "bcba@demo.com", "password": "demo123"})
    return resp.json()["access_token"]


def test_rejects_oversized_file():
    token = _login_token()
    # Create a file that exceeds 20MB limit
    big_file = io.BytesIO(b"x" * (21 * 1024 * 1024))
    resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"feature_id": "privacy_filter", "form_data": "{}"},
        files={"files": ("big.txt", big_file, "text/plain")},
    )
    assert resp.status_code == 413


def test_rejects_too_many_files():
    token = _login_token()
    files = [("files", (f"file{i}.txt", io.BytesIO(b"hello"), "text/plain")) for i in range(6)]
    resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"feature_id": "privacy_filter", "form_data": "{}"},
        files=files,
    )
    assert resp.status_code == 400
    assert "5" in resp.json()["detail"]


def test_accepts_valid_file():
    token = _login_token()
    small_file = io.BytesIO(b"test content")
    resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"feature_id": "privacy_filter", "form_data": "{}"},
        files={"files": ("test.txt", small_file, "text/plain")},
    )
    assert resp.status_code == 201
