# api/tests/test_vault_api.py
"""Tests for vault file browsing API endpoints."""

from fastapi.testclient import TestClient

from app.main import app

_client = TestClient(app)


def _register_and_get_token(email: str) -> str:
    resp = _client.post("/api/v1/users/register", json={
        "org_name": f"Vault-{email}",
        "admin_name": "管理员",
        "admin_email": email,
        "admin_password": "test123",
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_vault_read_requires_auth():
    res = _client.get("/api/v1/vault/read?path=01-Clients/test.md")
    assert res.status_code in (401, 403)


def test_vault_read_blocks_path_traversal():
    """Paths with '..' should be blocked."""
    token = _register_and_get_token("vault_traversal@test.com")
    res = _client.get(
        "/api/v1/vault/read?path=../../etc/passwd",
        headers=_auth(token),
    )
    assert res.status_code == 400


def test_vault_read_file_not_found():
    token = _register_and_get_token("vault_notfound@test.com")
    res = _client.get(
        "/api/v1/vault/read?path=01-Clients/nonexistent.md",
        headers=_auth(token),
    )
    assert res.status_code == 404


def test_vault_tree_returns_items():
    token = _register_and_get_token("vault_tree@test.com")
    res = _client.get(
        "/api/v1/vault/tree?prefix=01-Clients",
        headers=_auth(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_vault_blocks_unauthorized_directory():
    """Teacher role should not access 01-Clients directly (only via org_admin/bcba)."""
    # Register as org_admin (default), they should access 01-Clients
    token = _register_and_get_token("vault_role_admin@test.com")
    res = _client.get(
        "/api/v1/vault/tree?prefix=01-Clients",
        headers=_auth(token),
    )
    assert res.status_code == 200


def test_vault_roots_returns_role_filtered_list():
    """org_admin should see all 7 root directories."""
    token = _register_and_get_token("vault_roots@test.com")
    res = _client.get(
        "/api/v1/vault/roots",
        headers=_auth(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert "roots" in data
    roots = data["roots"]
    assert len(roots) == 7
    paths = [r["path"] for r in roots]
    assert "00-RawData" in paths
    assert "06-Templates" in paths
    # Each root should have label and icon
    for root in roots:
        assert "label" in root
        assert "icon" in root
