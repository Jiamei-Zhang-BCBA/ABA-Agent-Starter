"""
Tenant resolver middleware.
Extracts tenant context from the authenticated user for downstream services.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.user import User


@dataclass
class TenantContext:
    tenant_id: str
    plan_name: str
    user_id: str
    user_role: str


def resolve_tenant(user: User) -> TenantContext:
    """Build tenant context from authenticated user."""
    return TenantContext(
        tenant_id=user.tenant_id,
        plan_name=user.tenant.plan.name if user.tenant and user.tenant.plan else "starter",
        user_id=user.id,
        user_role=user.role,
    )
