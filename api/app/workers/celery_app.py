"""Celery application configuration. Gracefully handles missing Redis."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

celery_app = None

try:
    from celery import Celery
    from app.config import get_settings

    settings = get_settings()

    celery_app = Celery(
        "aba_worker",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.job_worker"],
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        task_soft_time_limit=300,  # 5 min soft limit
        task_time_limit=600,  # 10 min hard limit
        worker_max_tasks_per_child=50,
    )
except Exception as e:
    logger.warning("Celery/Redis not available, using local worker: %s", e)
    celery_app = None
