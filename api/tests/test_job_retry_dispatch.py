"""
BUG #17 regression test: when a job times out and enters retry flow,
the retry must actually be re-dispatched (a new worker thread must pick it up).

Before fix: job.status = QUEUED was set but no new thread was ever spawned,
so the job sat in the queue forever with input_tokens=0.

After fix: JobProcessor._reschedule_retry() spawns a delayed daemon thread
that calls process_job_background again.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from app.services.job_processor import JobProcessor


class TestRescheduleRetry:
    """Unit tests for JobProcessor._reschedule_retry (BUG #17 fix)."""

    def test_reschedule_retry_spawns_delayed_thread(self, monkeypatch):
        """Retry must dispatch the job again via local_worker after a delay."""
        # Speed up test: set delay to 0
        monkeypatch.setattr(
            "app.services.job_processor.RETRY_DELAY_SECONDS", 0
        )

        captured = []

        def fake_background(job_id):
            captured.append(job_id)
            return MagicMock()

        with patch(
            "app.services.local_worker.process_job_background",
            side_effect=fake_background,
        ):
            # Ensure Celery path is NOT taken
            with patch(
                "app.services.job_processor.settings"
            ) as fake_settings:
                fake_settings.redis_url = "redis://localhost:6379/0"  # default → local worker

                processor = JobProcessor()
                processor._reschedule_retry("job-abc-123")

                # Wait briefly for daemon thread to run
                time.sleep(0.3)

        assert captured == ["job-abc-123"], (
            "BUG #17 regression: retry must actually re-dispatch the job. "
            f"Expected one call with 'job-abc-123', got {captured}"
        )

    def test_reschedule_retry_uses_celery_when_configured(self, monkeypatch):
        """If a real Redis broker is configured, retry must dispatch via Celery."""
        monkeypatch.setattr(
            "app.services.job_processor.RETRY_DELAY_SECONDS", 0
        )

        celery_calls = []
        mock_task = MagicMock()
        mock_task.delay = lambda jid: celery_calls.append(jid)

        fake_celery_module = MagicMock()
        fake_celery_module.process_job_task = mock_task

        import sys
        sys.modules["app.workers.celery_app"] = fake_celery_module

        try:
            with patch(
                "app.services.job_processor.settings"
            ) as fake_settings:
                fake_settings.redis_url = "redis://prod-broker:6379/0"

                processor = JobProcessor()
                processor._reschedule_retry("job-celery-456")

                time.sleep(0.3)

            assert celery_calls == ["job-celery-456"], (
                f"Expected Celery dispatch, got {celery_calls}"
            )
        finally:
            del sys.modules["app.workers.celery_app"]

    def test_reschedule_retry_is_non_blocking(self, monkeypatch):
        """_reschedule_retry must return immediately, not block on the delay."""
        # Set a real delay of 2s — test must return well before this
        monkeypatch.setattr(
            "app.services.job_processor.RETRY_DELAY_SECONDS", 2
        )

        with patch("app.services.local_worker.process_job_background"):
            with patch(
                "app.services.job_processor.settings"
            ) as fake_settings:
                fake_settings.redis_url = "redis://localhost:6379/0"

                processor = JobProcessor()
                start = time.monotonic()
                processor._reschedule_retry("job-nb-789")
                elapsed = time.monotonic() - start

        assert elapsed < 0.5, (
            f"_reschedule_retry blocked for {elapsed:.2f}s — must be fire-and-forget. "
            "This would serialize all retries and defeat the fix for BUG #17."
        )

    def test_reschedule_retry_daemon_flag(self, monkeypatch):
        """Retry threads must be daemon=True so they don't block process shutdown.

        Uses a longer delay so we can catch the thread while it's sleeping.
        """
        monkeypatch.setattr(
            "app.services.job_processor.RETRY_DELAY_SECONDS", 5
        )

        threads_before = set(threading.enumerate())

        with patch("app.services.local_worker.process_job_background"):
            with patch(
                "app.services.job_processor.settings"
            ) as fake_settings:
                fake_settings.redis_url = "redis://localhost:6379/0"

                processor = JobProcessor()
                processor._reschedule_retry("job-daemon-999")

                # Retry thread should be alive (sleeping) right now
                time.sleep(0.1)
                new_threads = set(threading.enumerate()) - threads_before
                retry_threads = [t for t in new_threads if t.name.startswith("retry-")]

        assert len(retry_threads) >= 1, "Expected at least one retry-* thread"
        for t in retry_threads:
            assert t.daemon, f"Thread {t.name} must be daemon=True"


class TestProcessMethodReschedulesOnException:
    """Integration: JobProcessor.process() must call _reschedule_retry on failure."""

    def test_process_calls_reschedule_on_exception(self):
        """When _execute raises and retry_count < MAX_RETRIES, _reschedule_retry is called."""
        processor = JobProcessor()

        mock_db = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "job-xyz-321"
        mock_job.status = "queued"  # JobStatus.QUEUED.value
        mock_job.form_data_json = {}  # retry_count = 0

        # Mock db.execute().scalar_one_or_none() → mock_job
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_job

        # Patch _execute to raise, and _reschedule_retry to observe calls
        with patch.object(
            processor, "_execute", side_effect=TimeoutError("600s timeout")
        ), patch.object(
            processor, "_reschedule_retry"
        ) as mock_reschedule:
            processor.process(mock_db, "job-xyz-321")

        mock_reschedule.assert_called_once_with("job-xyz-321")

    def test_process_does_not_reschedule_after_max_retries(self):
        """When retry_count >= MAX_RETRIES, mark failed instead of retry."""
        processor = JobProcessor()

        mock_db = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "job-max-retry"
        mock_job.status = "queued"
        # MAX_RETRIES default is 2, so retry_count=2 means this attempt is the last
        mock_job.form_data_json = {"_retry_count": 2}

        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_job

        with patch.object(
            processor, "_execute", side_effect=TimeoutError("final timeout")
        ), patch.object(
            processor, "_reschedule_retry"
        ) as mock_reschedule, patch.object(
            processor, "_mark_failed"
        ) as mock_mark_failed:
            processor.process(mock_db, "job-max-retry")

        mock_reschedule.assert_not_called()
        mock_mark_failed.assert_called_once()
