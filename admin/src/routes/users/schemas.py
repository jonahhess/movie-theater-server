import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBaseSchema(BaseModel):
    username: str
    email: EmailStr
    phone: str | None

class UserCreateSchema(UserBaseSchema):
    password: str

class UserUpdateSchema(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    password: str | None = None

class UserResponseSchema(UserBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    created_at: datetime
