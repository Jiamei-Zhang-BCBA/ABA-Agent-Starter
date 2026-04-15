"""Usage and billing endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.usage_service import UsageService

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])

_svc = UsageService()


def _default_year_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


@router.get("/monthly")
async def monthly_usage(
    year_month: str = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ym = year_month or _default_year_month()
    return await _svc.get_monthly_summary(db, str(user.tenant_id), ym)


@router.get("/daily")
async def daily_usage(
    year_month: str = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ym = year_month or _default_year_month()
    breakdown = await _svc.get_daily_breakdown(db, str(user.tenant_id), ym)
    return {"year_month": ym, "breakdown": breakdown}
