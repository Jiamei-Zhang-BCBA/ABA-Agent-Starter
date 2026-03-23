"""
Audit logging service.
Records security-relevant actions for compliance and debugging.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Record an audit log entry. Fire-and-forget — never raises.

    Actions tracked:
    - user.registered, user.login, user.invited, user.updated, user.deleted
    - job.created, job.output_edited
    - review.approved, review.rejected
    - client.created, client.updated
    - password.reset_requested, password.reset_confirmed
    """
    try:
        entry = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail_json=detail or {},
            ip_address=ip_address,
        )
        db.add(entry)
        # Don't commit here — let the caller's transaction handle it.
        # If the caller doesn't commit, the audit log is lost, which is
        # acceptable (audit is best-effort, never blocks business logic).
        await db.flush()
    except Exception:
        logger.exception("Failed to write audit log: action=%s resource=%s/%s", action, resource_type, resource_id)
