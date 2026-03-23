"""
Local background worker for job processing without Celery/Redis.
Runs job processing in a background thread for local dev/testing.
Uses the unified JobProcessor for actual execution.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.services.job_processor import JobProcessor

logger = logging.getLogger(__name__)
settings = get_settings()

_processor = JobProcessor()


def _get_sync_url() -> str:
    """Convert async database URL to synchronous equivalent."""
    url = settings.database_url
    if "sqlite+aiosqlite" in url:
        return url.replace("sqlite+aiosqlite", "sqlite")
    if "postgresql+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql")
    return url


def _create_sync_engine():
    url = _get_sync_url()
    if "sqlite" in url:
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_size=5, max_overflow=10)


_sync_engine = _create_sync_engine()
SyncSession = sessionmaker(_sync_engine)


def process_job_sync(job_id: str) -> None:
    """Process a job synchronously using the unified JobProcessor."""
    with SyncSession() as db:
        _processor.process(db, job_id)


def process_job_background(job_id: str) -> threading.Thread:
    """
    Launch job processing in a background thread.
    Returns the thread handle for optional join/monitoring.
    """
    thread = threading.Thread(
        target=process_job_sync,
        args=(job_id,),
        name=f"job-worker-{job_id[:8]}",
        daemon=True,
    )
    thread.start()
    logger.info("Launched background thread for job %s", job_id)
    return thread
