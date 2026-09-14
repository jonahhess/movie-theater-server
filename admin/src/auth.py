import os
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.src.database import get_admin_db
from admin.src.models import Admin

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=ENV_PATH)

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXP_MINUTES = int(os.getenv("JWT_EXP_MINUTES", "15"))

bearer_scheme = HTTPBearer(auto_error=False)
security_credentials = Security(bearer_scheme)
db_session_dependency = Depends(get_admin_db)


async def validate_admin_authorization_header(
    authorization_header: str | None,
    db: AsyncSession,
) -> Admin:
    if not authorization_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization scheme must be Bearer",
        )

    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured",
        )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    admin_id = payload.get("sub")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required subject claim",
        )

    try:
        admin_uuid = uuid.UUID(str(admin_id))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is invalid",
        ) from exc

    admin = await db.scalar(
        select(Admin).where(Admin.id == admin_uuid, Admin.is_active.is_(True))
    )
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found or inactive",
        )

    return admin


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = security_credentials,
    db: AsyncSession = db_session_dependency,
) -> Admin:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    header_value = f"{credentials.scheme} {credentials.credentials}"
    return await validate_admin_authorization_header(header_value, db)


def verify_admin_login_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_admin_access_token(admin_user: Admin) -> str:
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured",
        )

    now = datetime.now(UTC)
    exp = now + timedelta(minutes=JWT_EXP_MINUTES)
    payload = {
        "sub": str(admin_user.id),
        "email": admin_user.email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
