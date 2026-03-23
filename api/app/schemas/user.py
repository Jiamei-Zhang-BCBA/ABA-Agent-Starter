from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# --- Registration ---

class TenantRegisterRequest(BaseModel):
    org_name: str = Field(..., min_length=2, max_length=200)
    admin_name: str = Field(..., min_length=2, max_length=100)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=6, max_length=128)
    plan_name: str = "starter"


class TenantRegisterResponse(BaseModel):
    tenant_id: str
    user_id: str
    email: str
    access_token: str
    refresh_token: str


# --- Invitation ---

class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: str = Field(..., pattern="^(bcba|teacher|parent)$")


class InvitationResponse(BaseModel):
    id: str
    email: str
    role: str
    token: str
    expires_at: datetime

    model_config = {"from_attributes": True}


class InvitationAcceptRequest(BaseModel):
    token: str
    name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)


# --- User Management ---

class UserUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    role: str | None = Field(None, pattern="^(org_admin|bcba|teacher|parent)$")
    is_active: bool | None = None


class UserDetailResponse(BaseModel):
    id: str
    tenant_id: str
    role: str
    name: str
    email: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserDetailResponse]
    total: int


# --- Password Reset ---

class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=128)
