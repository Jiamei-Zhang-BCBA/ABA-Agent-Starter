"""Tenant-level usage aggregation from Job table."""

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus

_COMPLETED = (JobStatus.DELIVERED.value, JobStatus.APPROVED.value)


class UsageService:

    async def get_monthly_summary(
        self, db: AsyncSession, tenant_id: str, year_month: str
    ) -> dict:
        """Aggregate token usage for a tenant in a given month (YYYY-MM)."""
        year, month = map(int, year_month.split("-"))

        stmt = (
            select(
                func.count(Job.id).label("total_jobs"),
                func.coalesce(func.sum(Job.input_tokens), 0).label("total_input_tokens"),
                func.coalesce(func.sum(Job.output_tokens), 0).label("total_output_tokens"),
                func.coalesce(func.sum(Job.cost_cents), 0).label("total_cost_cents"),
            )
            .where(
                Job.tenant_id == tenant_id,
                Job.status.in_(_COMPLETED),
                extract("year", Job.created_at) == year,
                extract("month", Job.created_at) == month,
            )
        )
        result = await db.execute(stmt)
        row = result.one()

        return {
            "year_month": year_month,
            "total_jobs": row.total_jobs,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "total_cost_cents": row.total_cost_cents,
        }

    async def get_daily_breakdown(
        self, db: AsyncSession, tenant_id: str, year_month: str
    ) -> list[dict]:
        """Per-day token usage breakdown for charts."""
        year, month = map(int, year_month.split("-"))

        stmt = (
            select(
                func.date(Job.created_at).label("day"),
                func.count(Job.id).label("jobs"),
                func.coalesce(func.sum(Job.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(Job.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(Job.cost_cents), 0).label("cost_cents"),
            )
            .where(
                Job.tenant_id == tenant_id,
                Job.status.in_(_COMPLETED),
                extract("year", Job.created_at) == year,
                extract("month", Job.created_at) == month,
            )
            .group_by(func.date(Job.created_at))
            .order_by(func.date(Job.created_at))
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "date": str(row.day),
                "jobs": row.jobs,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "cost_cents": row.cost_cents,
            }
            for row in rows
        ]
