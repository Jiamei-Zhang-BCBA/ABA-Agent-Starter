# api/tests/test_upload_limits.py
import io
from fastapi.testclient import TestClient
from app.main import app

_client = TestClient(app)


def _get_auth_token():
    """Register an org and return the admin's access token."""
    resp = _client.post("/api/v1/users/register", json={
        "org_name": "上传测试机构",
        "admin_name": "上传管理员",
        "admin_email": "upload-test@demo.com",
        "admin_password": "demo123",
    })
    if resp.status_code == 201:
        return resp.json()["access_token"]
    # Already registered — login instead
    resp = _client.post("/api/v1/auth/login", json={
        "email": "upload-test@demo.com", "password": "demo123",
    })
    return resp.json()["access_token"]


def test_rejects_oversized_file():
    token = _get_auth_token()
    # Create a file that exceeds 20MB limit
    big_file = io.BytesIO(b"x" * (21 * 1024 * 1024))
    resp = _client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"feature_id": "intake", "form_data": "{}"},
        files={"files": ("big.txt", big_file, "text/plain")},
    )
    assert resp.status_code == 413


def test_rejects_too_many_files():
    token = _get_auth_token()
    files = [("files", (f"file{i}.txt", io.BytesIO(b"hello"), "text/plain")) for i in range(6)]
    resp = _client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"feature_id": "intake", "form_data": "{}"},
        files=files,
    )
    assert resp.status_code == 400
    assert "5" in resp.json()["detail"]


def test_accepts_valid_file():
    import json
    token = _get_auth_token()
    small_file = io.BytesIO(b"test content")
    form_data = json.dumps({"child_alias": "测试儿童", "age": 5})
    resp = _client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"feature_id": "intake", "form_data": form_data},
        files={"files": ("test.txt", small_file, "text/plain")},
    )
    assert resp.status_code == 201
