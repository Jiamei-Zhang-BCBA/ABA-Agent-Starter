# api/tests/conftest.py
import asyncio
import os
import pytest
from fastapi.testclient import TestClient

# Use a dedicated test database to avoid interference with dev DB
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_aba.db")

from app.database import engine, Base, async_session
from app.models import *  # noqa: F401, F403 — ensure all models registered on Base
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables and seed plan data before any test runs."""

    async def _setup():
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        # Seed plans (required for registration tests)
        from app.models.tenant import Plan
        from app.core.plan_config import PLAN_CONFIGS

        async with async_session() as db:
            for name, config in PLAN_CONFIGS.items():
                plan = Plan(
                    name=name,
                    features_json={
                        "features": config.features
                        if isinstance(config.features, list)
                        else config.features
                    },
                    max_clients=config.max_clients,
                    max_staff=config.max_staff,
                    monthly_jobs=config.monthly_jobs,
                    price_cents=config.price_cents,
                )
                db.add(plan)
            await db.commit()

    asyncio.run(_setup())
    yield

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_teardown())

    # Clean up test database file
    try:
        os.remove("test_aba.db")
    except OSError:
        pass


@pytest.fixture
def client():
    """Sync test client for non-async tests."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset slowapi rate limiter storage between tests."""
    yield
    from app.middleware.rate_limiter import limiter
    limiter._limiter.storage.reset()
