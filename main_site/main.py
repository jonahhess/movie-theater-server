import os
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from admin.main import admin
from main_site.src.error_handlers import register_exception_handlers
from main_site.src.router import router
from tickets.main import tickets
from tickets.src import redis_client

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Mounted sub-apps don't receive ASGI lifespan events from the root app,
    # so their lifespans must be entered here explicitly.
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(redis_client.lifespan(tickets))
        yield


app = FastAPI(title="Main Root Application", lifespan=lifespan)

register_exception_handlers(app)

app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the sub-apps (their internal routes use their own database.py files)
app.mount("/admin", admin)
app.mount("/tickets", tickets)
