"""SSE (Server-Sent Events) endpoint for real-time job status updates."""

import asyncio
import json
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.models.user import User
from app.services.auth_service import get_current_user
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/jobs", tags=["stream"])

POLL_INTERVAL = 3  # seconds, fallback when Redis unavailable


async def _redis_event_generator(job_id: str, request: Request):
    """Listen to Redis pub/sub for job status changes."""
    settings = get_settings()
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"job:{job_id}")

        # Send initial keepalive
        yield f"event: connected\ndata: {json.dumps({'job_id': job_id})}\n\n"

        while True:
            if await request.is_disconnected():
                break

            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "message":
                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield f"event: status\ndata: {data}\n\n"

                # If terminal status, close stream
                parsed = json.loads(data)
                if parsed.get("status") in ("delivered", "approved", "failed", "rejected"):
                    yield f"event: complete\ndata: {data}\n\n"
                    break

            # Keepalive every 15 seconds
            yield ": keepalive\n\n"

        await pubsub.unsubscribe(f"job:{job_id}")
        await r.aclose()

    except Exception as e:
        logger.warning("Redis SSE unavailable, falling back to polling: %s", e)
        async for event in _polling_event_generator(job_id, request):
            yield event


async def _polling_event_generator(job_id: str, request: Request):
    """Fallback: poll database for job status changes."""
    from app.database import async_session
    from sqlalchemy import select
    from app.models.job import Job

    last_status = None
    not_found_count = 0
    yield f"event: connected\ndata: {json.dumps({'job_id': job_id, 'mode': 'polling'})}\n\n"

    while True:
        if await request.is_disconnected():
            break

        async with async_session() as db:
            result = await db.execute(select(Job.status).where(Job.id == job_id))
            row = result.scalar_one_or_none()

        if row is None:
            not_found_count += 1
            if not_found_count >= 3:
                yield f"event: error\ndata: {json.dumps({'job_id': job_id, 'error': 'job not found'})}\n\n"
                break
        elif row != last_status:
            last_status = row
            not_found_count = 0
            data = json.dumps({"job_id": job_id, "status": row})
            yield f"event: status\ndata: {data}\n\n"

            if row in ("delivered", "approved", "failed", "rejected"):
                yield f"event: complete\ndata: {data}\n\n"
                break

        await asyncio.sleep(POLL_INTERVAL)


@router.get("/{job_id}/stream")
async def job_status_stream(
    job_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    """SSE endpoint for real-time job status updates."""
    return StreamingResponse(
        _redis_event_generator(job_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
