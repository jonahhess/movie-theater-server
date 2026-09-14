import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from tickets.src.redis_seats import listen_for_expired_seat_holds

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = int(os.getenv("REDIS_DB", 0))

redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=REDIS_DB,
    decode_responses=True
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis_client
    expiry_listener = None

    try:
        await app.state.redis.ping()
        await app.state.redis.config_set("notify-keyspace-events", "Ex")
        expiry_listener = asyncio.create_task(
            listen_for_expired_seat_holds(app.state.redis)
        )
        print("Successfully connected to Redis.")
    except RedisError as e:
        print(f"Failed to connect to Redis on startup: {e}")

    yield

    if expiry_listener is not None:
        expiry_listener.cancel()
        try:
            await expiry_listener
        except asyncio.CancelledError:
            pass

    await app.state.redis.aclose()


def get_redis(request: Request) -> Redis:
    return request.app.state.redis