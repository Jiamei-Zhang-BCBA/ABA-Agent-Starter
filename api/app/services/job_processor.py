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
            else:
                self._mark_failed(db, job, str(exc))

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

            self._write_output_to_vault(vault, feature, client_code or "", result.output_content)

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
        """Execute skill with a timeout. Uses threading for cross-platform support."""
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
        thread.join(timeout=JOB_TIMEOUT_SECONDS)

        if thread.is_alive():
            raise JobTimeoutError(f"Job exceeded {JOB_TIMEOUT_SECONDS}s timeout")

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

    def _write_output_to_vault(self, vault, feature, client_code: str, content: str) -> None:
        """Write skill output to vault. Supports multi-file output via FILE markers."""
        import re

        # Check if output contains multi-file markers
        file_markers = list(re.finditer(
            r'<!--\s*FILE:\s*(.+?)(?:\s*\|\s*(APPEND))?\s*-->', content
        ))

        if file_markers:
            # Multi-file output: parse and write each file
            for i, marker in enumerate(file_markers):
                path = marker.group(1).strip()
                is_append = marker.group(2) is not None
                start = marker.end()
                end = file_markers[i + 1].start() if i + 1 < len(file_markers) else len(content)
                file_content = content[start:end].strip()

                if not file_content:
                    continue

                try:
                    if is_append:
                        existing = vault.read_file(path) or ""
                        vault.write_file(path, existing + "\n" + file_content)
                    else:
                        vault.write_file(path, file_content)
                    logger.info("Wrote vault file: %s (append=%s)", path, is_append)
                except Exception as e:
                    logger.error("Failed to write vault file %s: %s", path, e)
        else:
            # Single-file output: use default path mapping
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            path_map = {
                "session-reviewer": f"02-Sessions/Client-{client_code}-日志库/{today}-反馈.md",
                "parent-update": f"05-Communication/Client-{client_code}/{today}-家书.md",
                "teacher-guide": f"03-Staff/{today}-实操单-Client-{client_code}.md",
                "quick-summary": f"05-Communication/Client-{client_code}/{today}-简报.md",
                "staff-supervision": f"04-Supervision/{today}-听课反馈.md",
                "clinical-reflection": f"04-Supervision/{today}-周复盘.md",
                "reinforcer-tracker": f"01-Clients/Client-{client_code}/{today}-强化物评估.md",
                "privacy-filter": f"00-RawData/脱敏存档/{today}-Client-{client_code}-脱敏.md",
                "staff-onboarding": f"03-Staff/{today}-新教师建档.md",
            }
            path = path_map.get(feature._skill_name)
            if path:
                vault.write_file(path, content)

    def _mark_failed(self, db: Session, job: Job, error: str) -> None:
        """Mark a job as permanently failed."""
        job.status = JobStatus.FAILED.value
        job.error_message = error[:2000]
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
