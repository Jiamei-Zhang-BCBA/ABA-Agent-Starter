# api/tests/test_jwt_safety.py
import os
from unittest.mock import patch
from app.config import Settings


def test_dev_mode_generates_random_secret():
    """In dev (SQLite), default secret should be replaced with a random one."""
    s = Settings(database_url="sqlite+aiosqlite:///./test.db")
    assert s.jwt_secret_key != "change-me-to-a-random-secret-in-production"
    assert len(s.jwt_secret_key) >= 32


def test_prod_mode_rejects_default_secret():
    """In prod (PostgreSQL), default secret must raise an error."""
    import pytest
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(
            database_url="postgresql+asyncpg://x:x@localhost/db",
            jwt_secret_key="change-me-to-a-random-secret-in-production",
        )


def test_prod_mode_accepts_custom_secret():
    """In prod with a real secret, no error."""
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/db",
        jwt_secret_key="a-real-secret-that-is-long-enough-1234567890",
    )
    assert s.jwt_secret_key == "a-real-secret-that-is-long-enough-1234567890"
