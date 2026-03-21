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
from app.routers import auth, features, jobs, reviews, clients

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Startup: create tables (dev only, use Alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

# CORS middleware
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


# Serve static frontend files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


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
