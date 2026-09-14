import os
from hmac import compare_digest

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN")

api_key_scheme = APIKeyHeader(name="x_internal_service_token", auto_error=True)


def require_internal_service(x_internal_service_token: str = Depends(api_key_scheme),
) -> None:
    if not INTERNAL_SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal service token is not configured",
        )

    if not x_internal_service_token or not compare_digest(
        x_internal_service_token,
        INTERNAL_SERVICE_TOKEN,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")