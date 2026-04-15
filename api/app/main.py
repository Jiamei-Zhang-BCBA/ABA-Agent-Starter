"""
ABA Clinical Supervision SaaS API
Main FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import get_settings
from app.database import engine, Base
from app.routers import auth, features, jobs, reviews, clients, users

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
async def dashboard_overview():
    """Placeholder for dashboard data."""
    return {"message": "Dashboard endpoint — to be implemented in P2"}
