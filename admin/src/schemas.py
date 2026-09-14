from datetime import datetime

from pydantic import BaseModel, EmailStr


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class AdminMeResponse(BaseModel):
    id: str
    email: EmailStr
    is_active: bool
    created_at: datetime