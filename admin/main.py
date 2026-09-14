from fastapi import FastAPI

from admin.src.error_handlers import register_exception_handlers
from admin.src.router import protected_router, public_router

admin = FastAPI(title="Admin")

register_exception_handlers(admin)

admin.include_router(public_router)
admin.include_router(protected_router)
