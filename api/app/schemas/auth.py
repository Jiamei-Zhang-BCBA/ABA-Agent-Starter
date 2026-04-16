from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str
    captcha_id: str | None = None
    captcha_answer: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    role: str
    name: str
    email: str

    model_config = {"from_attributes": True}
