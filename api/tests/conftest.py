# api/tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    """Sync test client for non-async tests."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset slowapi rate limiter storage between tests."""
    yield
    from app.middleware.rate_limiter import limiter
    limiter._limiter.storage.reset()
