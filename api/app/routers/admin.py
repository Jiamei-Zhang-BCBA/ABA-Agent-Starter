"""Super-admin endpoints: manage tenants, plans, system-wide operations."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.tenant import Tenant, Plan
from app.models.invitation import Invitation
from app.services.auth_service import require_super_admin
from app.services import user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Roles that super-admin can invite into a target tenant (covers org_admin
# so an organization can be re-seeded with a new admin if needed).
_INVITABLE_ROLES = {
    UserRole.ORG_ADMIN.value,
    UserRole.BCBA.value,
    UserRole.TEACHER.value,
    UserRole.PARENT.value,
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TenantCreateRequest(BaseModel):
    org_name: str = Field(..., min_length=2, max_length=200)
    admin_name: str = Field(..., min_length=2, max_length=100)
    admin_email: str
    admin_password: str = Field(..., min_length=6, max_length=128)
    plan_name: str = "starter"


class TenantResponse(BaseModel):
    id: str
    name: str
    plan_name: str | None = None
    client_count: int = 0
    user_count: int = 0

    class Config:
        from_attributes = True


class PlanUpdateRequest(BaseModel):
    plan_name: str


class TenantInvitationRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    role: str = Field(..., description="org_admin | bcba | teacher | parent")


class TenantInvitationResponse(BaseModel):
    id: str
    email: str
    role: str
    token: str
    expires_at: str
    accept_url: str | None = None  # full /invite?token=... path for sharing


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/tenants")
async def list_tenants(
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all tenants (super-admin only)."""
    from sqlalchemy import func
    from app.models.client import Client

    stmt = select(Tenant).options()
    result = await db.execute(stmt)
    tenants = result.scalars().all()

    items = []
    for t in tenants:
        user_count = (await db.execute(
            select(func.count(User.id)).where(User.tenant_id == t.id)
        )).scalar() or 0
        client_count = (await db.execute(
            select(func.count(Client.id)).where(Client.tenant_id == str(t.id))
        )).scalar() or 0

        plan_name = None
        if t.plan_id:
            plan_result = await db.execute(select(Plan.name).where(Plan.id == t.plan_id))
            plan_name = plan_result.scalar_one_or_none()

        items.append({
            "id": str(t.id),
            "name": t.name,
            "plan_name": plan_name,
            "user_count": user_count,
            "client_count": client_count,
        })

    return {"tenants": items}


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_tenant(
    req: TenantCreateRequest,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tenant with its first admin (super-admin only)."""
    try:
        result = await user_service.register_tenant(
            db,
            org_name=req.org_name,
            admin_name=req.admin_name,
            admin_email=req.admin_email,
            admin_password=req.admin_password,
            plan_name=req.plan_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    logger.info("Super-admin %s created tenant: %s", user.email, req.org_name)
    return result


@router.patch("/tenants/{tenant_id}/plan")
async def update_tenant_plan(
    tenant_id: str,
    req: PlanUpdateRequest,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Change a tenant's subscription plan (super-admin only)."""
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="租户不存在")

    plan_result = await db.execute(select(Plan).where(Plan.name == req.plan_name))
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=400, detail=f"未知的套餐: {req.plan_name}")

    tenant.plan_id = plan.id
    db.add(tenant)
    await db.commit()

    logger.info("Super-admin %s changed tenant %s plan to %s", user.email, tenant_id, req.plan_name)
    return {"tenant_id": tenant_id, "plan_name": req.plan_name, "message": "套餐已更新"}


# ---------------------------------------------------------------------------
# Cross-tenant user invitation (super-admin only)
# ---------------------------------------------------------------------------

@router.post(
    "/tenants/{tenant_id}/invitations",
    response_model=TenantInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tenant_invitation(
    tenant_id: str,
    req: TenantInvitationRequest,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Super-admin: invite a user (any role) into the specified tenant.

    Returns the raw invitation token plus a relative accept URL the
    super-admin can share with the invitee.
    """
    if req.role not in _INVITABLE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"无效角色：{req.role}（允许：{', '.join(sorted(_INVITABLE_ROLES))}）",
        )

    # Verify tenant exists
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    if tenant_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="租户不存在")

    try:
        invitation = await user_service.create_invitation(
            db,
            inviter=user,
            email=req.email,
            role=req.role,
            target_tenant_id=tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "Super-admin %s invited %s as %s into tenant %s",
        user.email, req.email, req.role, tenant_id,
    )

    return TenantInvitationResponse(
        id=str(invitation.id),
        email=invitation.email,
        role=invitation.role,
        token=invitation.token,
        expires_at=invitation.expires_at.isoformat(),
        accept_url=f"/invite?token={invitation.token}",
    )


@router.get("/tenants/{tenant_id}/invitations")
async def list_tenant_invitations(
    tenant_id: str,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Super-admin: list pending (un-accepted, un-expired) invitations for a tenant."""
    from datetime import datetime
    now = datetime.utcnow()

    stmt = (
        select(Invitation)
        .where(
            Invitation.tenant_id == tenant_id,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > now,
        )
        .order_by(Invitation.expires_at.desc())
    )
    result = await db.execute(stmt)
    invitations = result.scalars().all()

    return {
        "invitations": [
            {
                "id": str(inv.id),
                "email": inv.email,
                "role": inv.role,
                "token": inv.token,
                "expires_at": inv.expires_at.isoformat(),
                "accept_url": f"/invite?token={inv.token}",
            }
            for inv in invitations
        ]
    }


@router.get("/auth-config")
async def get_auth_config():
    """Public endpoint: return registration/captcha config for frontend."""
    from app.config import get_settings
    s = get_settings()
    return {
        "registration_enabled": s.registration_enabled,
        "captcha_enabled": s.captcha_enabled,
    }
