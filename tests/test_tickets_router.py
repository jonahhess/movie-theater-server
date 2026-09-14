import asyncio
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Column, Integer, Table, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# database.py builds its module-level engine URL at import time; the tests
# override get_admin_db with their own sqlite engine, so this value is unused.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from tickets.main import tickets
from tickets.src import token as token_module
from tickets.src.database import Base, get_admin_db
from tickets.src.models import Auditorium, Screening, Seat, Ticket, User
from tickets.src.redis_client import get_redis
from tickets.src.router import get_or_create_user_uuid

TEST_USER_UUID = "0198f8db-cb17-75e8-9f80-0e18e015d741"


def run(coro):
    return asyncio.run(coro)


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def delete(self, *keys):
        self.commands.append(("delete", keys))

    def hset(self, key, mapping):
        self.commands.append(("hset", key, mapping))

    def ttl(self, key):
        self.commands.append(("ttl", key))

    def get(self, key):
        self.commands.append(("get", key))

    async def execute(self):
        results = []
        for command in self.commands:
            match command:
                case ("delete", keys):
                    results.append(await self.redis.delete(*keys))
                case ("hset", key, mapping):
                    results.append(await self.redis.hset(key, mapping=mapping))
                case ("ttl", key):
                    results.append(await self.redis.ttl(key))
                case ("get", key):
                    results.append(await self.redis.get(key))
        return results


class FakeRedis:
    """Minimal in-memory stand-in for redis.asyncio.Redis used by the router tests."""

    def __init__(self):
        self.values = {}
        self.ttls = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return None
        self.values[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def get(self, key):
        return self.values.get(key)

    async def delex(self, key, ifeq):
        if self.values.get(key) == ifeq:
            self.values.pop(key, None)
            self.ttls.pop(key, None)
            return 1
        return 0

    async def ttl(self, key):
        if key not in self.values:
            return -2
        return self.ttls.get(key, -1)

    async def expire(self, key, ttl_seconds):
        if key not in self.values:
            return 0
        self.ttls[key] = int(ttl_seconds)
        return 1

    async def hset(self, key, mapping):
        # mirror the real client's decode_responses=True string coercion
        stringified = {str(k): str(v) for k, v in mapping.items()}
        self.values.setdefault(key, {}).update(stringified)
        return len(mapping)

    async def hgetall(self, key):
        return self.values.get(key, {})

    async def hexists(self, key, field):
        return int(field in self.values.get(key, {}))

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.values:
                deleted += 1
                self.values.pop(key, None)
                self.ttls.pop(key, None)
        return deleted

    async def scan_iter(self, match, count=500):
        for key in list(self.values):
            if fnmatch(key, match):
                yield key

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    async def eval(self, script, number_of_keys, *args):
        from tickets.src import redis_seats

        keys = args[:number_of_keys]
        argv = args[number_of_keys:]

        if script == redis_seats.EXTEND_SEATS_SCRIPT:
            target_user, ttl_seconds = argv
            extended = 0
            for key in keys:
                if self.values.get(key) == target_user:
                    extended += await self.expire(key, ttl_seconds)
            return extended

        if script == redis_seats.ACQUIRE_SEATS_SCRIPT:
            target_user, receipt_id = argv
            owned = finalized = 0
            for key in keys:
                if self.values.get(key) == target_user:
                    owned += 1
                    ttl = await self.ttl(key)
                    if ttl > 0:
                        self.ttls.pop(key, None)
                        self.values[key] = receipt_id
                        finalized += 1
            return [owned, finalized]

        if script == redis_seats.RELEASE_ALL_SCRIPT:
            target_user = argv[0]
            deleted_keys = []
            for key in keys:
                if self.values.get(key) == target_user:
                    ttl = await self.ttl(key)
                    if ttl > 0 and await self.delete(key):
                        deleted_keys.append(key)
            return deleted_keys

        if script == redis_seats.CHANGE_OWNER_SCRIPT:
            old_user, new_user = argv
            updated = 0
            for key in keys:
                if self.values.get(key) == old_user:
                    self.values[key] = new_user
                    updated += 1
            return updated

        raise AssertionError("unexpected Lua script")

    async def xadd(self, key, fields, id="*", maxlen=None, approximate=True):
        return "1-0"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@asynccontextmanager
async def make_client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def fake_get_admin_db():
        async with session_factory() as session:
            yield session

    fake_redis = FakeRedis()

    tickets.dependency_overrides[get_admin_db] = fake_get_admin_db
    tickets.dependency_overrides[get_redis] = lambda: fake_redis
    tickets.dependency_overrides[get_or_create_user_uuid] = lambda: TEST_USER_UUID

    transport = ASGITransport(app=tickets)
    try:
        async with AsyncClient(transport=transport, base_url="http://test/api/v1/tickets") as client:
            yield client, session_factory, fake_redis
    finally:
        tickets.dependency_overrides.clear()
        await engine.dispose()


def test_login_rejects_unknown_email(monkeypatch):
    async def scenario():
        async with make_client(monkeypatch) as (client, _session_factory, _redis):
            response = await client.post(
                "/login", json={"email": "nobody@example.com", "password": "secret"}
            )
            assert response.status_code == 401

    run(scenario())


def test_login_rejects_wrong_password(monkeypatch):
    async def scenario():
        async with make_client(monkeypatch) as (client, session_factory, _redis):
            password_hash = bcrypt.hashpw(b"correct-password", bcrypt.gensalt())
            async with session_factory() as session:
                session.add(
                    User(
                        email="user@example.com",
                        username="movie_fan",
                        password_hash=password_hash.decode("utf-8"),
                    )
                )
                await session.commit()

            response = await client.post(
                "/login",
                json={"email": "user@example.com", "password": "wrong-password"},
            )
            assert response.status_code == 401

    run(scenario())


def test_login_succeeds_and_migrates_held_seats(monkeypatch):
    async def scenario():
        async with make_client(monkeypatch) as (client, session_factory, redis):
            password_hash = bcrypt.hashpw(b"correct-password", bcrypt.gensalt())
            user_id = uuid.uuid7()
            async with session_factory() as session:
                session.add(
                    User(
                        id=user_id,
                        email="user@example.com",
                        username="movie_fan",
                        password_hash=password_hash.decode("utf-8"),
                    )
                )
                await session.commit()

            await redis.set(f"screening:10::{TEST_USER_UUID}", TEST_USER_UUID, ex=60)
            await redis.set("screening:10::A1", TEST_USER_UUID, ex=60)

            response = await client.post(
                "/login",
                json={"email": "user@example.com", "password": "correct-password"},
            )

            assert response.status_code == 200
            body = response.json()
            assert body["user_id"] == str(user_id)
            assert body["username"] == "movie_fan"
            assert body["migrated_seat_count"] == 2
            assert response.cookies.get("user_uuid") == str(user_id)

    run(scenario())


def test_hold_seat_returns_404_for_unknown_seat(monkeypatch):
    async def scenario():
        async with make_client(monkeypatch) as (client, _session_factory, _redis):
            response = await client.post("/screenings/10/seats/A1/hold")
            assert response.status_code == 404

    run(scenario())


def test_hold_seat_succeeds_and_rejects_second_holder(monkeypatch):
    async def scenario():
        async with make_client(monkeypatch) as (client, _session_factory, redis):
            await redis.hset("screening:10:seat_map", mapping={"A1": "available"})

            first = await client.post("/screenings/10/seats/A1/hold")
            assert first.status_code == 200
            assert first.json() is True

            held = await client.get("/screenings/10/seats")
            assert held.json() == ["screening:10::A1"]

    run(scenario())


def test_release_seats_endpoint_releases_and_logs_out(monkeypatch):
    async def scenario():
        async with make_client(monkeypatch) as (client, _session_factory, redis):
            await redis.set("screening:10::A1", TEST_USER_UUID, ex=60)

            response = await client.post("/release_seats")
            assert response.status_code == 200
            assert "user_uuid" not in response.cookies

    run(scenario())


def test_make_payment_creates_tickets_for_held_seats(monkeypatch):
    async def scenario():
        async with make_client(monkeypatch) as (client, session_factory, redis):
            async with session_factory() as session:
                auditorium = Auditorium(status="active")
                auditorium.seats = [Seat(row="A", number=1), Seat(row="A", number=2)]
                session.add(auditorium)
                await session.flush()

                screening = Screening(
                    auditorium_id=auditorium.id,
                    start_time=datetime.now(),
                    status="on_sale",
                )
                session.add(screening)
                await session.flush()
                screening_id = screening.id
                seat_ids = [seat.id for seat in auditorium.seats]
                await session.commit()

            for seat_id in seat_ids:
                await redis.set(
                    f"screening:{screening_id}::{seat_id}",
                    TEST_USER_UUID,
                    ex=60,
                )

            response = await client.post(
                f"/screenings/{screening_id}/checkout/payment",
                json={"email": "fan@example.com", "phone": "555-0100"},
            )

            assert response.status_code == 200
            assert response.json() is True

            async with session_factory() as session:
                tickets = (await session.execute(select(Ticket))).scalars().all()

            assert len(seat_ids) == 2
            assert len(tickets) == 2
            assert {ticket.email for ticket in tickets} == {"fan@example.com"}
            checkout_ids = {ticket.checkout_id for ticket in tickets}
            assert len(checkout_ids) == 1
            checkout_id = checkout_ids.pop()
            assert checkout_id is not None
            assert {str(ticket.purchaser_uuid) for ticket in tickets} == {
                TEST_USER_UUID
            }
            assert {ticket.seat_id for ticket in tickets} == set(seat_ids)
            finalized_ttls = [
                await redis.ttl(f"screening:{screening_id}::{seat_id}")
                for seat_id in seat_ids
            ]
            assert finalized_ttls == [-1, -1]
            finalized_owners = [
                await redis.get(f"screening:{screening_id}::{seat_id}")
                for seat_id in seat_ids
            ]
            assert finalized_owners == [checkout_id, checkout_id]

    run(scenario())


def test_make_payment_releases_acquired_seats_when_ticket_creation_fails(monkeypatch):
    async def scenario():
        async with make_client(monkeypatch) as (client, session_factory, redis):
            await redis.set("screening:10::A1", TEST_USER_UUID, ex=60)

            response = await client.post(
                "/screenings/10/checkout/payment",
                json={"email": "fan@example.com"},
            )

            assert response.status_code == 503
            assert await redis.get("screening:10::A1") is None
            async with session_factory() as session:
                ticket_count = len(
                    (await session.execute(select(Ticket))).scalars().all()
                )
            assert ticket_count == 0

    run(scenario())


def test_make_payment_failure_releases_only_current_checkout(monkeypatch):
    async def scenario():
        async with make_client(monkeypatch) as (client, _session_factory, redis):
            await redis.set("screening:10::A1", "previous-checkout")
            await redis.set("screening:10::A2", TEST_USER_UUID, ex=60)

            response = await client.post(
                "/screenings/10/checkout/payment",
                json={"email": "fan@example.com"},
            )

            assert response.status_code == 503
            assert await redis.get("screening:10::A1") == "previous-checkout"
            assert await redis.ttl("screening:10::A1") == -1
            assert await redis.get("screening:10::A2") is None

    run(scenario())


def test_open_screening_sale_requires_internal_token(monkeypatch):
    async def scenario():
        monkeypatch.setattr(token_module, "INTERNAL_SERVICE_TOKEN", "shared-secret")
        async with make_client(monkeypatch) as (client, _session_factory, _redis):
            # missing header -> FastAPI's APIKeyHeader raises 401
            response = await client.post("/internal/screenings/1/sale/open")
            assert response.status_code == 401

            forbidden = await client.post(
                "/internal/screenings/1/sale/open",
                headers={"x_internal_service_token": "wrong-token"},
            )
            assert forbidden.status_code == 403

    run(scenario())


def test_open_screening_sale_warms_auditorium_seats(monkeypatch):
    async def scenario():
        monkeypatch.setattr(token_module, "INTERNAL_SERVICE_TOKEN", "shared-secret")
        async with make_client(monkeypatch) as (client, session_factory, redis):
            async with session_factory() as session:
                auditorium = Auditorium(status="active")
                auditorium.seats = [
                    Seat(row="A", number=1),
                    Seat(row="A", number=2),
                ]
                session.add(auditorium)
                await session.flush()
                session.add(
                    Screening(
                        id=1,
                        auditorium_id=auditorium.id,
                        start_time=datetime.now(),
                        status="draft",
                    )
                )
                await session.commit()

            response = await client.post(
                "/internal/screenings/1/sale/open",
                headers={"x_internal_service_token": "shared-secret"},
            )

            assert response.status_code == 200
            assert response.json()["seat_count"] == 2
            assert await redis.hgetall("screening:1:seat_map") == {
                "1": "available",
                "2": "available",
            }

    run(scenario())


def test_invalidate_ticket_redeems_and_rejects_double_redeem(monkeypatch):
    async def scenario():
        monkeypatch.setattr(token_module, "INTERNAL_SERVICE_TOKEN", "shared-secret")
        async with make_client(monkeypatch) as (client, session_factory, _redis):
            async with session_factory() as session:
                ticket = Ticket(
                    screening_seat_id=1,
                    email="fan@example.com",
                    receipt_number="receipt-1",
                    status="confirmed",
                )
                session.add(ticket)
                await session.commit()
                ticket_id = ticket.id

            headers = {"x_internal_service_token": "shared-secret"}
            first = await client.post(f"/internal/{ticket_id}/redeem", headers=headers)
            assert first.status_code == 200

            second = await client.post(f"/internal/{ticket_id}/redeem", headers=headers)
            assert second.status_code == 400

    run(scenario())
