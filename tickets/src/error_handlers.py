import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

logger = logging.getLogger(__name__)


def _is_schema_missing_db_error(exc: DBAPIError) -> bool:
    details = str(getattr(exc, "orig", exc)).lower()
    schema_missing_markers = ("no such table", "doesn't exist", "unknown table", "1146")
    return any(marker in details for marker in schema_missing_markers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DBAPIError)
    async def handle_db_errors(_: Request, exc: DBAPIError):
        if _is_schema_missing_db_error(exc):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Database schema is not ready yet. \
                         Please try again later."},
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Database query failed."},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_errors(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exceptions(_: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_errors(request: Request, exc: Exception):
        logger.exception(
            "unhandled tickets exception: %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
        )