"""
Job processing worker.
Handles the full lifecycle: parse files -> execute skill -> route to review or deliver.
Supports both Celery (production) and local thread-based (dev) execution.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.workers.celery_app import celery_app
from app.models.job import Job, JobStatus, Upload, ParseStatus
from app.models.review import Review, ReviewStatus
from app.models.client import Client
from app.core.feature_registry import get_feature
from app.services.vault_service import create_vault_service
from app.services.file_processor import parse_file
from app.services.skill_executor import SkillExecutor

logger = logging.getLogger(__name__)
settings = get_settings()


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


sync_engine = _create_sync_engine()
SyncSession = sessionmaker(sync_engine)


# Only define the Celery task if celery is available
if celery_app is not None:
    @celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
    def process_job_task(self, job_id: str):
        """
        Main job processing task (Celery).
        1. Parse uploaded files
        2. Execute skill via Claude API
        3. Route to review queue or deliver directly
        """
        with SyncSession() as db:
            try:
                _process_job(db, job_id)
            except Exception as exc:
                logger.exception("Job %s failed: %s", job_id, exc)
                _mark_job_failed(db, job_id, str(exc))
                raise self.retry(exc=exc)
else:
    process_job_task = None


def process_job_sync(job_id: str) -> None:
    """Process a job synchronously (for local dev without Celery)."""
    with SyncSession() as db:
        try:
            _process_job(db, job_id)
        except Exception as exc:
            logger.exception("Job %s failed: %s", job_id, exc)
            _mark_job_failed(db, job_id, str(exc))


def _process_job(db: Session, job_id: str):
    """Core job processing logic."""
    job = db.execute(select(Job).where(Job.id == job_id)).scalar_one()

    feature = get_feature(job.feature_id)
    if feature is None:
        raise ValueError(f"Unknown feature: {job.feature_id}")

    # --- Step 1: Parse uploaded files ---
    job.status = JobStatus.PARSING.value
    db.commit()

    parsed_uploads = _parse_uploads(db, job)

    # --- Step 2: Execute skill ---
    job.status = JobStatus.PROCESSING.value
    db.commit()

    # Resolve client code name for vault context
    client_code = None
    if job.client_id:
        client = db.execute(select(Client).where(Client.id == job.client_id)).scalar_one_or_none()
        if client:
            client_code = client.code_name

    vault = create_vault_service(str(job.tenant_id))
    executor = SkillExecutor(vault)

    result = executor.execute(
        feature=feature,
        form_data=job.form_data_json,
        parsed_uploads=parsed_uploads,
        client_code=client_code,
    )

    job.input_tokens = result.input_tokens
    job.output_tokens = result.output_tokens
    # Rough cost estimate: Sonnet ~$3/MTok input, $15/MTok output
    job.cost_cents = int((result.input_tokens * 0.3 + result.output_tokens * 1.5) / 100)

    # --- Step 3: Route based on review tier ---
    if feature._review_tier == "expert":
        # Enter review queue
        review = Review(
            job_id=job.id,
            output_content=result.output_content,
            status=ReviewStatus.PENDING.value,
        )
        db.add(review)
        job.status = JobStatus.PENDING_REVIEW.value
    else:
        # Direct delivery
        job.output_content = result.output_content
        job.status = JobStatus.DELIVERED.value
        job.completed_at = datetime.now(timezone.utc)

        # Write output to vault
        if client_code:
            from app.services.vault_service import write_output_to_vault
            write_output_to_vault(vault, feature._skill_name, client_code, result.output_content)

    db.commit()
    logger.info("Job %s completed with status: %s", job_id, job.status)


def _parse_uploads(db: Session, job: Job) -> list[str]:
    """Parse all uploaded files for a job and return their text content."""
    uploads = db.execute(
        select(Upload).where(Upload.job_id == job.id)
    ).scalars().all()

    parsed = []
    vault = create_vault_service(str(job.tenant_id))

    for upload in uploads:
        try:
            upload.parse_status = ParseStatus.PROCESSING.value
            db.commit()

            file_bytes = vault.read_raw_file(upload.storage_path)
            text = parse_file(file_bytes, upload.original_filename)

            upload.parsed_content = text
            upload.parse_status = ParseStatus.COMPLETED.value
            db.commit()

            parsed.append(text)
        except Exception as e:
            logger.error("Failed to parse upload %s: %s", upload.id, e)
            upload.parse_status = ParseStatus.FAILED.value
            db.commit()
            parsed.append(f"[文件解析失败: {upload.original_filename}]")

    return parsed


def _mark_job_failed(db: Session, job_id: str, error: str):
    """Mark a job as failed."""
    try:
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if job:
            job.status = JobStatus.FAILED.value
            job.error_message = error[:2000]  # truncate
            db.commit()
    except Exception:
        logger.exception("Failed to mark job %s as failed", job_id)
