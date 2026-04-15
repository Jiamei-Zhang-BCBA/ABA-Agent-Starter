"""
ABA Clinical Supervision SaaS API
Main FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import engine, Base, get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.routers import auth, features, jobs, reviews, clients, users, usage, stream, vault

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Startup: create tables only for SQLite (dev mode).
    # In production (PostgreSQL), use Alembic migrations instead.
    if "sqlite" in settings.database_url:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Seed default plans if none exist (dev convenience)
    from app.database import async_session
    from sqlalchemy import select
    from app.models.tenant import Plan
    from app.core.plan_config import PLAN_CONFIGS
    async with async_session() as db:
        result = await db.execute(select(Plan).limit(1))
        if result.scalar_one_or_none() is None:
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
            logger.info("Seeded %d default plans", len(PLAN_CONFIGS))

    # Initialize storage backend
    if settings.storage_mode == "local":
        # Create local storage directories
        storage_root = Path(settings.local_storage_path)
        storage_root.mkdir(parents=True, exist_ok=True)
        logger.info("Local storage mode: files at %s", storage_root.resolve())
    else:
        # Ensure MinIO bucket exists
        try:
            from app.services.vault_service import _get_s3_client
            s3 = _get_s3_client()
            try:
                s3.head_bucket(Bucket=settings.minio_bucket)
            except Exception:
                s3.create_bucket(Bucket=settings.minio_bucket)
        except Exception as e:
            logger.warning("Could not initialize MinIO bucket: %s", e)

    # Ensure all existing clients have vault directories
    try:
        from app.models.client import Client
        from app.services.vault_service import create_vault_service, init_client_vault
        async with async_session() as db:
            clients = (await db.execute(select(Client))).scalars().all()
            for client in clients:
                vault = create_vault_service(str(client.tenant_id))
                init_client_vault(vault, client.code_name)
            if clients:
                logger.info("Verified vault directories for %d clients", len(clients))
    except Exception:
        logger.exception("Failed to verify client vault directories")

    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="ABA 临床督导 SaaS API",
    description="将 ABA 临床督导系统封装为云端 API 服务",
    version="0.1.0",
    lifespan=lifespan,
)

# Structured logging middleware (added BEFORE CORS so CORS executes first)
from app.middleware.logging_middleware import StructuredLoggingMiddleware
app.add_middleware(StructuredLoggingMiddleware)

# CORS middleware (must be the LAST added so it runs FIRST)
settings = get_settings()
_cors_kwargs: dict = {
    "allow_origins": settings.cors_origins,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.cors_origin_regex:
    _cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex
logger.info("CORS config: origins=%s, regex=%s", settings.cors_origins, settings.cors_origin_regex)
app.add_middleware(CORSMiddleware, **_cors_kwargs)

# Rate limiting
from app.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Register routers
app.include_router(auth.router)
app.include_router(features.router)
app.include_router(jobs.router)
app.include_router(reviews.router)
app.include_router(clients.router)
app.include_router(users.router)
app.include_router(usage.router)
app.include_router(stream.router)
app.include_router(vault.router)


# Serve static frontend files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
async def health():
    """Enhanced health check: DB connectivity, storage, active jobs."""
    from app.database import async_session
    from sqlalchemy import text, select, func
    from app.models.job import Job, JobStatus

    checks = {"version": "0.1.0"}
    all_ok = True

    # Database check
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
            # Active job count
            result = await db.execute(
                select(func.count(Job.id)).where(
                    Job.status.in_([JobStatus.QUEUED.value, JobStatus.PARSING.value, JobStatus.PROCESSING.value])
                )
            )
            checks["active_jobs"] = result.scalar() or 0
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        all_ok = False

    # Storage check
    try:
        _settings = get_settings()
        if _settings.storage_mode == "local":
            storage_root = Path(_settings.local_storage_path)
            checks["storage"] = "ok" if storage_root.exists() else "error: path not found"
            if not storage_root.exists():
                all_ok = False
        else:
            checks["storage"] = "s3 (not checked in health)"
    except Exception as e:
        checks["storage"] = f"error: {e}"
        all_ok = False

    checks["status"] = "ok" if all_ok else "degraded"

    from fastapi.responses import JSONResponse
    status_code = 200 if all_ok else 503
    return JSONResponse(content=checks, status_code=status_code)


@app.get("/")
async def root():
    """Serve the frontend SPA."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Frontend not found. Visit /docs for API documentation."}


@app.get("/api/v1/dashboard/overview")
async def dashboard_overview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard overview: KPIs, recent jobs, pending reviews."""
    from datetime import datetime, timezone
    from sqlalchemy import select, func, extract
    from app.models.job import Job, JobStatus
    from app.models.client import Client
    from app.models.review import Review, ReviewStatus
    from app.services.usage_service import UsageService

    tenant_id = str(user.tenant_id)
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month

    # Total clients
    client_count = await db.execute(
        select(func.count(Client.id)).where(Client.tenant_id == tenant_id)
    )
    total_clients = client_count.scalar() or 0

    # Jobs this month
    job_month = await db.execute(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant_id,
            extract("year", Job.created_at) == year,
            extract("month", Job.created_at) == month,
        )
    )
    total_jobs_this_month = job_month.scalar() or 0

    # Completed jobs this month
    completed = await db.execute(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant_id,
            Job.status.in_((JobStatus.DELIVERED.value, JobStatus.APPROVED.value)),
            extract("year", Job.created_at) == year,
            extract("month", Job.created_at) == month,
        )
    )
    completed_count = completed.scalar() or 0
    completion_rate = round(completed_count / total_jobs_this_month * 100) if total_jobs_this_month > 0 else 0

    # Token usage summary
    svc = UsageService()
    ym = now.strftime("%Y-%m")
    token_usage = await svc.get_monthly_summary(db, tenant_id, ym)

    # Recent jobs (last 10)
    recent_result = await db.execute(
        select(Job.id, Job.feature_id, Job.status, Job.created_at)
        .where(Job.tenant_id == tenant_id)
        .order_by(Job.created_at.desc())
        .limit(10)
    )
    recent_jobs = [
        {
            "id": str(row.id),
            "feature_id": row.feature_id,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in recent_result.all()
    ]

    # Pending reviews
    pending_result = await db.execute(
        select(func.count(Review.id))
        .join(Job, Review.job_id == Job.id)
        .where(
            Job.tenant_id == tenant_id,
            Review.status == ReviewStatus.PENDING.value,
        )
    )
    pending_reviews = pending_result.scalar() or 0

    return {
        "total_clients": total_clients,
        "total_jobs_this_month": total_jobs_this_month,
        "completion_rate": completion_rate,
        "token_usage": token_usage,
        "recent_jobs": recent_jobs,
        "pending_reviews": pending_reviews,
    }
