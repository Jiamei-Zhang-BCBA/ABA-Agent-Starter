"""
Unified JobProcessor — used by both Celery worker and local background thread.
Handles parsing, skill execution, review routing, timeout, and retry.
"""

from __future__ import annotations

import logging
import signal
import threading
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.job import Job, JobStatus, Upload, ParseStatus
from app.models.review import Review, ReviewStatus
from app.models.client import Client
from app.core.feature_registry import get_feature
from app.services.vault_service import create_vault_service
from app.services.file_processor import parse_file
from app.services.skill_executor import SkillExecutor
from app.core.pricing import calculate_cost_cents

logger = logging.getLogger(__name__)
settings = get_settings()

# Configuration
JOB_TIMEOUT_SECONDS = int(getattr(settings, "job_timeout_seconds", 300))
MAX_RETRIES = int(getattr(settings, "job_max_retries", 2))
RETRY_DELAY_SECONDS = int(getattr(settings, "job_retry_delay_seconds", 30))

# BUG #26 (v5 2026-04-19): per-feature timeout override for long-form expert skills.
# plan_generator produces the largest structured output (IEP + BIP + schedules combined);
# after commit 627def1 加了 S-xx 硬规则，opus 模型在 expert tier 稳定超 600s。
# 这些 skill 的 timeout 放宽到 1200s（仍有 MAX_RETRIES 兜底）。
FEATURE_TIMEOUT_OVERRIDE_SECONDS = {
    "plan_generator": 1200,
    "transfer_protocol": 1200,
    "milestone_report": 1200,
}


class JobTimeoutError(Exception):
    """Raised when a job exceeds its time limit."""


class JobProcessor:
    """
    Stateless job processor. Call process(db, job_id) to run a job.
    Handles retry logic internally.
    """

    def process(self, db: Session, job_id: str) -> None:
        """Process a job with retry support."""
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if job is None:
            logger.error("Job %s not found", job_id)
            return

        # Check if job was cancelled before we start
        if job.status not in (JobStatus.QUEUED.value, JobStatus.FAILED.value):
            logger.info("Job %s has status %s, skipping", job_id, job.status)
            return

        retry_count = job.form_data_json.get("_retry_count", 0) if job.form_data_json else 0

        try:
            self._execute(db, job)
        except Exception as exc:
            logger.exception("Job %s failed (attempt %d/%d): %s", job_id, retry_count + 1, MAX_RETRIES + 1, exc)

            if retry_count < MAX_RETRIES:
                # Schedule retry
                form_data = dict(job.form_data_json) if job.form_data_json else {}
                form_data["_retry_count"] = retry_count + 1
                job.form_data_json = form_data
                job.status = JobStatus.QUEUED.value
                job.error_message = f"Retry {retry_count + 1}/{MAX_RETRIES}: {str(exc)[:500]}"
                db.commit()
                logger.info("Job %s queued for retry %d/%d", job_id, retry_count + 1, MAX_RETRIES)

                # BUG #17 fix: actually re-dispatch the job. Without this, the QUEUED status
                # just sits forever because nothing else polls the queue in local-worker mode.
                # We delay by RETRY_DELAY_SECONDS to avoid tight retry loops.
                self._reschedule_retry(job_id)
            else:
                self._mark_failed(db, job, str(exc))

    def _reschedule_retry(self, job_id: str) -> None:
        """Re-dispatch a job for retry. In local-worker mode, spawn a new daemon
        thread after RETRY_DELAY_SECONDS. In Celery mode, enqueue on the broker.

        Without this, BUG #17: jobs set to QUEUED during retry never run again
        because local_worker only starts a thread once at POST /jobs time.
        """
        import time

        def _delayed_dispatch():
            if RETRY_DELAY_SECONDS > 0:
                time.sleep(RETRY_DELAY_SECONDS)
            try:
                # Prefer Celery if a real broker is configured
                if settings.redis_url and settings.redis_url != "redis://localhost:6379/0":
                    from app.workers.celery_app import process_job_task  # type: ignore
                    process_job_task.delay(job_id)
                    logger.info("Job %s retry dispatched via Celery", job_id)
                else:
                    from app.services.local_worker import process_job_background
                    process_job_background(job_id)
                    logger.info("Job %s retry dispatched via local worker", job_id)
            except Exception:
                logger.exception("Failed to reschedule retry for job %s", job_id)

        # Fire-and-forget daemon thread so we don't block the current worker thread
        t = threading.Thread(target=_delayed_dispatch, name=f"retry-{job_id[:8]}", daemon=True)
        t.start()

    def _execute(self, db: Session, job: Job) -> None:
        """Core execution logic with timeout."""
        feature = get_feature(job.feature_id)
        if feature is None:
            raise ValueError(f"Unknown feature: {job.feature_id}")

        # --- Step 1: Parse uploads ---
        job.status = JobStatus.PARSING.value
        db.commit()
        self._publish_status(job)

        parsed_uploads = self._parse_uploads(db, job)

        # --- Step 2: Execute skill (with timeout) ---
        job.status = JobStatus.PROCESSING.value
        db.commit()
        self._publish_status(job)

        client_code = None
        if job.client_id:
            client = db.execute(select(Client).where(Client.id == job.client_id)).scalar_one_or_none()
            if client:
                client_code = client.code_name

        vault = create_vault_service(str(job.tenant_id))
        executor = SkillExecutor(vault)

        result = self._execute_with_timeout(
            executor, feature, job.form_data_json, parsed_uploads, client_code
        )

        job.input_tokens = result.input_tokens
        job.output_tokens = result.output_tokens
        job.cost_cents = calculate_cost_cents(result.model_used, result.input_tokens, result.output_tokens)

        # --- Step 3: Route based on review tier ---
        if feature._review_tier == "expert":
            review = Review(
                job_id=job.id,
                output_content=result.output_content,
                status=ReviewStatus.PENDING.value,
            )
            db.add(review)
            job.status = JobStatus.PENDING_REVIEW.value
        else:
            job.output_content = result.output_content
            job.status = JobStatus.DELIVERED.value
            job.completed_at = datetime.now(timezone.utc)

            from app.services.vault_service import write_output_to_vault
            write_output_to_vault(vault, feature._skill_name, client_code or "", result.output_content)

        db.commit()
        self._publish_status(job)
        logger.info("Job %s completed with status: %s", job.id, job.status)

    def _publish_status(self, job: Job) -> None:
        """Publish job status change to Redis for SSE listeners."""
        try:
            import redis as redis_lib
            import json
            r = redis_lib.Redis.from_url(settings.redis_url)
            r.publish(f"job:{job.id}", json.dumps({
                "status": job.status,
                "job_id": str(job.id),
            }))
        except Exception:
            pass  # Redis unavailable, SSE clients will fallback to polling

    def _execute_with_timeout(self, executor, feature, form_data, parsed_uploads, client_code):
        """Execute skill with a timeout. Uses threading for cross-platform support.

        BUG #26 fix: use per-feature timeout override for long-form expert skills
        (plan_generator / transfer_protocol / milestone_report). Falls back to
        JOB_TIMEOUT_SECONDS for all other features.
        """
        feature_id = getattr(feature, "id", None) or getattr(feature, "_skill_name", None)
        timeout_seconds = FEATURE_TIMEOUT_OVERRIDE_SECONDS.get(feature_id, JOB_TIMEOUT_SECONDS)

        result_holder = [None]
        error_holder = [None]

        def _run():
            try:
                result_holder[0] = executor.execute(
                    feature=feature,
                    form_data=form_data,
                    parsed_uploads=parsed_uploads,
                    client_code=client_code,
                )
            except Exception as e:
                error_holder[0] = e

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            raise JobTimeoutError(f"Job exceeded {timeout_seconds}s timeout")

        if error_holder[0]:
            raise error_holder[0]

        return result_holder[0]

    def _parse_uploads(self, db: Session, job: Job) -> list[str]:
        """Parse all uploaded files for a job."""
        uploads = db.execute(select(Upload).where(Upload.job_id == job.id)).scalars().all()
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

    def _mark_failed(self, db: Session, job: Job, error: str) -> None:
        """Mark a job as permanently failed."""
        job.status = JobStatus.FAILED.value
        job.error_message = error[:2000]
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
