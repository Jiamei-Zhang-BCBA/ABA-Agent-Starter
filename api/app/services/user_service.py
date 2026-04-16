"""
User management service.
Handles registration, invitation, password reset, and user CRUD.
"""

import secrets
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    """Timezone-aware UTC now, stripped to naive for SQLite compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.user import User, UserRole
from app.models.tenant import Tenant, Plan
from app.models.invitation import Invitation
from app.models.password_reset import PasswordResetToken
from app.services.auth_service import hash_password, create_access_token, create_refresh_token
from app.services.audit_service import log_action


# --- Registration ---

async def register_tenant(
    db: AsyncSession,
    org_name: str,
    admin_name: str,
    admin_email: str,
    admin_password: str,
    plan_name: str = "starter",
) -> dict:
    """Create a new tenant with its first org_admin user."""
    # Check email not already taken
    existing = await db.execute(select(User).where(User.email == admin_email))
    if existing.scalar_one_or_none() is not None:
        raise ValueError("该邮箱已被注册")

    # Lookup plan
    plan_result = await db.execute(select(Plan).where(Plan.name == plan_name))
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise ValueError(f"未知的套餐: {plan_name}")

    # Create tenant
    tenant = Tenant(
        name=org_name,
        plan_id=plan.id,
        settings_json={"language": "zh-CN"},
    )
    db.add(tenant)
    await db.flush()

    # Create org_admin user
    user = User(
        tenant_id=tenant.id,
        role=UserRole.ORG_ADMIN.value,
        name=admin_name,
        email=admin_email,
        password_hash=hash_password(admin_password),
    )
    db.add(user)
    await db.flush()

    await db.flush()
    await log_action(
        db, tenant_id=str(tenant.id), user_id=str(user.id),
        action="user.registered", resource_type="tenant", resource_id=str(tenant.id),
        detail={"org_name": org_name, "plan": plan_name},
    )
    await db.commit()
    await db.refresh(user)

    return {
        "tenant_id": tenant.id,
        "user_id": user.id,
        "email": user.email,
        "access_token": create_access_token(str(user.id), str(tenant.id), user.role),
        "refresh_token": create_refresh_token(str(user.id)),
    }


# --- Invitation ---

async def create_invitation(
    db: AsyncSession,
    inviter: User,
    email: str,
    role: str,
    target_tenant_id: str | None = None,
) -> Invitation:
    """
    Create an invitation for a new user to join a tenant.

    By default the invitation goes to the inviter's own tenant. If
    `target_tenant_id` is provided, the invitation goes to that tenant
    instead — used by super-admin to seed users into any organization.
    """
    # Org-admin invitations are only allowed via the super-admin path
    # (target_tenant_id explicitly set), since regular org_admins create
    # peers via the tenant-registration flow.
    if role == UserRole.ORG_ADMIN.value and target_tenant_id is None:
        raise ValueError("不能邀请 org_admin 角色，请通过注册创建")

    tenant_id = target_tenant_id or inviter.tenant_id

    # Check email not already in target tenant
    existing = await db.execute(
        select(User).where(User.email == email, User.tenant_id == tenant_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("该邮箱已在该机构注册")

    invitation = Invitation(
        tenant_id=tenant_id,
        email=email,
        role=role,
        token=secrets.token_urlsafe(32),
        invited_by=inviter.id,
        expires_at=_utcnow() + timedelta(days=7),
    )
    db.add(invitation)
    await db.flush()
    await log_action(
        db, tenant_id=str(tenant_id), user_id=str(inviter.id),
        action="user.invited",
        resource_type="invitation",
        resource_id=str(invitation.id),
        detail={
            "email": email,
            "role": role,
            "by_super_admin": target_tenant_id is not None,
        },
    )
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def accept_invitation(
    db: AsyncSession,
    token: str,
    name: str,
    password: str,
) -> dict:
    """Accept an invitation and create the user account."""
    result = await db.execute(
        select(Invitation).where(Invitation.token == token)
    )
    invitation = result.scalar_one_or_none()

    if invitation is None:
        raise ValueError("无效的邀请链接")

    if invitation.accepted_at is not None:
        raise ValueError("该邀请已被使用")

    if invitation.expires_at < _utcnow():
        raise ValueError("邀请链接已过期")

    # Check email not taken
    existing = await db.execute(select(User).where(User.email == invitation.email))
    if existing.scalar_one_or_none() is not None:
        raise ValueError("该邮箱已被注册")

    # Create user
    user = User(
        tenant_id=invitation.tenant_id,
        role=invitation.role,
        name=name,
        email=invitation.email,
        password_hash=hash_password(password),
    )
    db.add(user)

    # Mark invitation as accepted
    invitation.accepted_at = _utcnow()
    db.add(invitation)

    await db.commit()
    await db.refresh(user)

    return {
        "tenant_id": invitation.tenant_id,
        "user_id": user.id,
        "email": user.email,
        "access_token": create_access_token(str(user.id), str(invitation.tenant_id), user.role),
        "refresh_token": create_refresh_token(str(user.id)),
    }


# --- User CRUD ---

async def list_users(
    db: AsyncSession,
    tenant_id: str,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[User], int]:
    """List users in a tenant with pagination."""
    conditions = [User.tenant_id == tenant_id]
    stmt = (
        select(User)
        .where(and_(*conditions))
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    users = list(result.scalars().all())

    count_stmt = select(func.count(User.id)).where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar()

    return users, total


async def get_user(db: AsyncSession, tenant_id: str, user_id: str) -> User:
    """Get a user by ID within the same tenant."""
    stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("用户不存在")
    return user


async def update_user(
    db: AsyncSession,
    admin: User,
    target_user_id: str,
    name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> User:
    """Update a user's profile (org_admin only, same tenant)."""
    target = await get_user(db, admin.tenant_id, target_user_id)

    # Cannot modify yourself via this endpoint
    if target.id == admin.id:
        raise ValueError("不能通过此接口修改自己的信息")

    # Cannot demote the last org_admin
    if role is not None and target.role == UserRole.ORG_ADMIN.value and role != UserRole.ORG_ADMIN.value:
        admin_count = (await db.execute(
            select(func.count(User.id)).where(
                User.tenant_id == admin.tenant_id,
                User.role == UserRole.ORG_ADMIN.value,
                User.is_active == True,
            )
        )).scalar()
        if admin_count <= 1:
            raise ValueError("不能降级最后一个管理员")

    if name is not None:
        target.name = name
    if role is not None:
        target.role = role
    if is_active is not None:
        target.is_active = is_active

    db.add(target)
    await db.commit()
    await db.refresh(target)
    return target


async def soft_delete_user(db: AsyncSession, admin: User, target_user_id: str) -> User:
    """Soft-delete a user (set is_active=False)."""
    if target_user_id == admin.id:
        raise ValueError("不能删除自己")
    result = await update_user(db, admin, target_user_id, is_active=False)
    await log_action(
        db, tenant_id=str(admin.tenant_id), user_id=str(admin.id),
        action="user.deleted", resource_type="user", resource_id=target_user_id,
    )
    await db.commit()
    return result


# --- Password Reset ---

async def request_password_reset(db: AsyncSession, email: str) -> str | None:
    """
    Create a password reset token. Returns token if user exists, None otherwise.
    Callers should always return success to prevent email enumeration.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return None

    token_obj = PasswordResetToken(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=_utcnow() + timedelta(hours=1),
    )
    db.add(token_obj)
    await db.commit()
    return token_obj.token


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> None:
    """Confirm password reset with token."""
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    )
    token_obj = result.scalar_one_or_none()

    if token_obj is None:
        raise ValueError("无效的重置链接")

    if token_obj.used_at is not None:
        raise ValueError("该重置链接已被使用")

    if token_obj.expires_at < _utcnow():
        raise ValueError("重置链接已过期")

    # Update password
    user_result = await db.execute(select(User).where(User.id == token_obj.user_id))
    user = user_result.scalar_one()
    user.password_hash = hash_password(new_password)
    db.add(user)

    # Mark token as used
    token_obj.used_at = _utcnow()
    db.add(token_obj)

    await db.commit()
