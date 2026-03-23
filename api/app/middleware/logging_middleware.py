"""
Structured JSON logging middleware.
Attaches request_id, user_id, tenant_id to every request log.
"""

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.access")


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        # Extract user info from JWT if available
        user_id = None
        tenant_id = None
        try:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                from jose import jwt
                from app.config import get_settings
                settings = get_settings()
                payload = jwt.decode(
                    auth_header[7:],
                    settings.jwt_secret_key,
                    algorithms=[settings.jwt_algorithm],
                    options={"verify_exp": False},
                )
                user_id = payload.get("sub")
                tenant_id = payload.get("tenant_id")
        except Exception:
            pass

        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "ip": request.client.host if request.client else None,
        }

        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(level, json.dumps(log_data, ensure_ascii=False))

        response.headers["X-Request-ID"] = request_id
        return response
