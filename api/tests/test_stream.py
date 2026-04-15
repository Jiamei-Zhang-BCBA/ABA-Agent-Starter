# api/tests/test_stream.py
"""Tests for SSE streaming endpoint."""

import asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app

_transport = ASGITransport(app=app)


def _register_and_get_token() -> str:
    """Register via sync TestClient, return token."""
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/api/v1/users/register", json={
        "org_name": "Stream-Test",
        "admin_name": "管理员",
        "admin_email": "stream_test@test.com",
        "admin_password": "test123",
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


def test_stream_requires_auth():
    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.get("/api/v1/jobs/fake-id/stream")
    assert res.status_code in (401, 403)


def test_stream_endpoint_exists_and_returns_sse():
    """SSE endpoint should return text/event-stream content type with initial event."""
    token = _register_and_get_token()

    async def _test():
        async with AsyncClient(transport=_transport, base_url="http://test") as ac:
            async with ac.stream(
                "GET",
                "/api/v1/jobs/fake-id/stream",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15.0,
            ) as res:
                # Verify content-type header
                content_type = res.headers.get("content-type", "")
                assert "text/event-stream" in content_type

                # Read the initial connected event
                collected = b""
                async for chunk in res.aiter_bytes():
                    collected += chunk
                    # After getting initial event, check and break
                    if b"event:" in collected:
                        break

                text = collected.decode("utf-8")
                assert "event:" in text

    asyncio.run(_test())
