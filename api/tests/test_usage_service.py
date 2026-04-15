# api/tests/test_usage_service.py
"""Tests for UsageService — tenant monthly/daily token aggregation."""

import asyncio
import uuid
from datetime import datetime, timezone

from app.database import async_session
from app.models.job import Job, JobStatus
from app.services.usage_service import UsageService


_svc = UsageService()
_tenant_id = str(uuid.uuid4())


def _run(coro):
    return asyncio.run(coro)


def test_get_monthly_summary_empty():
    """No jobs for a random tenant → zero totals."""
    async def _test():
        async with async_session() as db:
            result = await _svc.get_monthly_summary(db, tenant_id=_tenant_id, year_month="2026-04")
            assert result["total_jobs"] == 0
            assert result["total_input_tokens"] == 0
            assert result["total_output_tokens"] == 0
            assert result["total_cost_cents"] == 0

    _run(_test())


def test_get_monthly_summary_with_jobs():
    """Completed jobs should be aggregated."""
    tid = str(uuid.uuid4())

    async def _setup_and_test():
        async with async_session() as db:
            job = Job(
                tenant_id=tid,
                user_id="u1",
                feature_id="session_review",
                status=JobStatus.DELIVERED.value,
                input_tokens=1000,
                output_tokens=500,
                cost_cents=10,
            )
            db.add(job)
            await db.commit()

        async with async_session() as db:
            ym = datetime.now(timezone.utc).strftime("%Y-%m")
            result = await _svc.get_monthly_summary(db, tenant_id=tid, year_month=ym)
            assert result["total_jobs"] == 1
            assert result["total_input_tokens"] == 1000
            assert result["total_output_tokens"] == 500
            assert result["total_cost_cents"] == 10

    _run(_setup_and_test())


def test_get_daily_breakdown():
    """Daily breakdown returns list of per-day stats."""
    async def _test():
        async with async_session() as db:
            result = await _svc.get_daily_breakdown(db, tenant_id=_tenant_id, year_month="2026-04")
            assert isinstance(result, list)

    _run(_test())
