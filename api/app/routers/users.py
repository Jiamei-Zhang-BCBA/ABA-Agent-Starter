"""User management endpoints: registration, invitation, CRUD, password reset."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import get_current_user, require_roles
from app.middleware.rate_limiter import limiter
from app.schemas.user import (
    TenantRegisterRequest,
    TenantRegisterResponse,
    InvitationCreateRequest,
    InvitationResponse,
    InvitationAcceptRequest,
    UserUpdateRequest,
    UserDetailResponse,
    UserListResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from app.services import user_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# --- Registration ---

@router.post("/register", response_model=TenantRegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(request: Request, req: TenantRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new organization with its first admin user."""
    from app.config import get_settings
    if not get_settings().registration_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="公开注册已关闭，请联系管理员",
        )
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
    return result


# --- Invitation ---

@router.post("/invite", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    req: InvitationCreateRequest,
    user: User = Depends(require_roles(UserRole.ORG_ADMIN.value)),
    db: AsyncSession = Depends(get_db),
):
    """Invite a new user to join the organization."""
    try:
        invitation = await user_service.create_invitation(db, user, req.email, req.role)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return invitation


@router.post("/invite/accept", response_model=TenantRegisterResponse, status_code=status.HTTP_201_CREATED)
async def accept_invite(req: InvitationAcceptRequest, db: AsyncSession = Depends(get_db)):
    """Accept an invitation and create a user account."""
    try:
        result = await user_service.accept_invitation(db, req.token, req.name, req.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result


# --- User CRUD ---

@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = 0,
    limit: int = 20,
    user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.BCBA.value)),
    db: AsyncSession = Depends(get_db),
):
    """List users in the current organization."""
    users, total = await user_service.list_users(db, user.tenant_id, skip, limit)
    return UserListResponse(users=users, total=total)


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: str,
    user: User = Depends(require_roles(UserRole.ORG_ADMIN.value, UserRole.BCBA.value)),
    db: AsyncSession = Depends(get_db),
):
    """Get user details within the same organization."""
    try:
        target = await user_service.get_user(db, user.tenant_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return target


@router.patch("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    user: User = Depends(require_roles(UserRole.ORG_ADMIN.value)),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's name, role, or active status."""
    try:
        target = await user_service.update_user(
            db, user, user_id,
            name=req.name,
            role=req.role,
            is_active=req.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return target


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    user: User = Depends(require_roles(UserRole.ORG_ADMIN.value)),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a user (set is_active=False)."""
    try:
        await user_service.soft_delete_user(db, user, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Password Reset ---

@router.post("/password-reset", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def request_password_reset(
    request: Request,
    req: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset token. Always returns success to prevent email enumeration."""
    await user_service.request_password_reset(db, req.email)
    return {"detail": "如果该邮箱已注册，重置链接将发送至邮箱"}


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
async def confirm_password_reset(req: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    """Confirm password reset with token and new password."""
    try:
        await user_service.confirm_password_reset(db, req.token, req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"detail": "密码已重置，请重新登录"}
