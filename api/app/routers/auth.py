"""Auth endpoints: login, refresh, me, captcha."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, UserResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.services.captcha_service import generate_captcha, verify_captcha
from app.models.user import User

from app.middleware.rate_limiter import limiter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/captcha")
async def get_captcha():
    """Generate a math CAPTCHA for login."""
    return generate_captcha()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Verify CAPTCHA if enabled
    settings = get_settings()
    if settings.captcha_enabled:
        if not req.captcha_id or not req.captcha_answer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请完成验证码",
            )
        if not verify_captcha(req.captcha_id, req.captcha_answer):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误或已过期",
            )

    user = await authenticate_user(db, req.email, req.password)

    from app.services.audit_service import log_action
    await log_action(
        db, tenant_id=str(user.tenant_id), user_id=str(user.id),
        action="user.login", resource_type="user", resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id), str(user.tenant_id), user.role),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload["sub"]
    # Re-fetch user to get current role/tenant
    from sqlalchemy import select
    from app.models.user import User as UserModel
    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one()

    return TokenResponse(
        access_token=create_access_token(str(user.id), str(user.tenant_id), user.role),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
