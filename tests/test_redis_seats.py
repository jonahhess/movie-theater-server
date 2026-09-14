import asyncio
import sys
from fnmatch import fnmatch
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tickets.src import redis_seats


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

    def ttl(self, key):
        self.commands.append(("ttl", key))

    def get(self, key):
        self.commands.append(("get", key))

    def hset(self, key, mapping):
        self.commands.append(("hset", key, mapping))

    def delete(self, *keys):
        self.commands.append(("delete", keys))

    def expire(self, key, ttl_seconds):
        self.commands.append(("expire", key, ttl_seconds))

    async def execute(self):
        results = []
        for command in self.commands:
            match command:
                case ("ttl", key):
                    results.append(await self.redis.ttl(key))
                case ("get", key):
                    results.append(await self.redis.get(key))
                case ("hset", key, mapping):
                    results.append(await self.redis.hset(key, mapping=mapping))
                case ("delete", keys):
                    results.append(await self.redis.delete(*keys))
                case ("expire", key, ttl_seconds):
                    results.append(await self.redis.expire(key, ttl_seconds))
        return results


class FakePubSub:
    def __init__(self, messages):
        self.messages = messages
        self.subscribed_channels = []
        self.unsubscribed_channels = []
        self.closed = False

    async def subscribe(self, channel):
        self.subscribed_channels.append(channel)

    async def unsubscribe(self, channel):
        self.unsubscribed_channels.append(channel)

    async def psubscribe(self, pattern):
        self.subscribed_channels.append(pattern)

    async def punsubscribe(self, pattern):
        self.unsubscribed_channels.append(pattern)

    async def aclose(self):
        self.closed = True

    async def listen(self):
        for message in self.messages:
            yield message


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.streams = {}
        self.pubsub_messages = []
        self.pubsub_instance = None

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
        self.values.setdefault(key, {}).update(mapping)
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

    def pubsub(self):
        self.pubsub_instance = FakePubSub(self.pubsub_messages)
        return self.pubsub_instance

    async def eval(self, script, number_of_keys, *args):
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
            owned = 0
            finalized = 0
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

        raise AssertionError("unexpected Lua script")

    async def xadd(self, key, fields, id="*", maxlen=None, approximate=True):
        message_id = "1-0"
        self.streams.setdefault(key, []).append((message_id, fields))
        return message_id

    async def xread(self, streams, count=1, block=5000):
        stream_key = next(iter(streams))
        messages = self.streams.get(stream_key, [])[:count]
        if not messages:
            return []
        return [(stream_key, messages)]


def test_reserve_seat_sets_temporary_lock_and_rejects_duplicate_holder():
    async def scenario():
        redis = FakeRedis()

        first_attempt = await redis_seats.reserve_seat(
            redis, "10", "A1", "user-1", lock_ttl_seconds=60
        )
        second_attempt = await redis_seats.reserve_seat(
            redis, "10", "A1", "user-2", lock_ttl_seconds=60
        )

        assert first_attempt is True
        assert second_attempt is False
        assert await redis.get("screening:10::A1") == "user-1"
        assert await redis.ttl("screening:10::A1") == 60
        assert len(redis.streams["stream:screening:10"]) == 1
        msg_id, payload = redis.streams["stream:screening:10"][0]
        assert payload["seat_id"] == "A1"
        assert payload["status"] == "locked"
        assert "owner_tag" in payload

    run(scenario())


def test_release_seat_only_deletes_matching_user_lock():
    async def scenario():
        redis = FakeRedis()
        await redis.set("screening:10::A1", "user-1", ex=60)

        released_by_other_user = await redis_seats.release_seat(
            redis, "10", "A1", "user-2"
        )
        assert released_by_other_user is False
        assert await redis.get("screening:10::A1") == "user-1"
        assert redis.streams == {}

        released_by_owner = await redis_seats.release_seat(redis, "10", "A1", "user-1")
        assert released_by_owner is True
        assert await redis.get("screening:10::A1") is None
        assert redis.streams == {
            "stream:screening:10": [
                ("1-0", {"seat_id": "A1", "status": "available", "owner_tag": ""})
            ]
        }

    run(scenario())


def test_get_user_held_seats_returns_only_current_users_temporary_locks():
    async def scenario():
        redis = FakeRedis()
        await redis.set("screening:10::A1", "user-1", ex=60)
        await redis.set("screening:10::A2", "user-1")
        await redis.set("screening:10::A3", "user-2", ex=60)
        await redis.set("screening:11::A1", "user-1", ex=60)

        held = await redis_seats.get_user_held_seats(redis, "10", "user-1")

        assert held == ["screening:10::A1"]

    run(scenario())


def test_extend_seat_hold_refreshes_all_matching_user_locks():
    async def scenario():
        redis = FakeRedis()
        await redis.set("screening:10::A1", "user-1", ex=60)
        await redis.set("screening:10::A2", "user-1", ex=60)
        await redis.set("screening:10::A3", "user-2", ex=60)

        extended = await redis_seats.extend_seat_hold(
            redis, "10", "user-1", ttl_seconds=300
        )

        assert extended is True
        assert await redis.ttl("screening:10::A1") == 300
        assert await redis.ttl("screening:10::A2") == 300
        assert await redis.ttl("screening:10::A3") == 60

    run(scenario())


def test_acquire_seats_persists_owned_locks():
    async def scenario():
        redis = FakeRedis()
        await redis.set("screening:10::A1", "user-1", ex=60)
        await redis.set("screening:10::A2", "user-1", ex=60)
        await redis.set("screening:10::A3", "user-2", ex=60)

        acquired = await redis_seats.acquire_seats(
            redis, "10", "user-1", "receipt-1"
        )

        assert acquired is True
        assert await redis.ttl("screening:10::A1") == -1
        assert await redis.ttl("screening:10::A2") == -1
        assert await redis.ttl("screening:10::A3") == 60
        assert await redis.get("screening:10::A1") == "receipt-1"
        assert await redis.get("screening:10::A2") == "receipt-1"
        assert await redis.get("screening:10::A3") == "user-2"
        assert redis.streams == {
            "stream:screening:10": [
                ("1-0", {"seat_id": "A1", "status": "purchased", "owner_tag": ""}),
                ("1-0", {"seat_id": "A2", "status": "purchased", "owner_tag": ""}),
            ]
        }

    run(scenario())


def test_release_all_seats_deletes_only_matching_user_locks():
    async def scenario():
        redis = FakeRedis()
        await redis.set("screening:10::A1", "user-1", ex=60)
        await redis.set("screening:10::A2", "user-1", ex=60)
        await redis.set("screening:10::A3", "user-2", ex=60)

        released = await redis_seats.release_all_seats(redis, "10", "user-1")

        assert released == 2
        assert await redis.get("screening:10::A1") is None
        assert await redis.get("screening:10::A2") is None
        assert await redis.get("screening:10::A3") == "user-2"
        assert redis.streams == {
            "stream:screening:10": [
                ("1-0", {"seat_id": "A1", "status": "available", "owner_tag": ""}),
                ("1-0", {"seat_id": "A2", "status": "available", "owner_tag": ""}),
            ]
        }

    run(scenario())


def test_release_all_lua_script_reads_first_argument_as_target_user():
    assert "local target_user = ARGV[1]" in redis_seats.RELEASE_ALL_SCRIPT


def test_warm_screening_seats_loads_valid_seats_for_screening():
    async def scenario():
        redis = FakeRedis()
        await redis.hset(
            "screening:10:seat_map",
            mapping={"OLD": "available"},
        )

        await redis_seats.warm_screening_seats(redis, "10", ["A1", "A2", "B1"])

        assert await redis.hgetall("screening:10:seat_map") == {
            "A1": "available",
            "A2": "available",
            "B1": "available",
        }
        assert await redis_seats.seat_exists(redis, "10", "A1") is True
        assert await redis_seats.seat_exists(redis, "10", "OLD") is False
        assert await redis_seats.seat_exists(redis, "10", "Z9") is False

    run(scenario())


def test_warm_screening_seats_requires_at_least_one_seat():
    async def scenario():
        redis = FakeRedis()

        with pytest.raises(ValueError, match="seat_ids"):
            await redis_seats.warm_screening_seats(redis, "10", [])

    run(scenario())


def test_warm_screening_cache_stores_strings_and_optional_ttl():
    async def scenario():
        redis = FakeRedis()

        await redis_seats.warm_screening_cache(
            redis,
            "screening:10:details",
            {"title": "Alien", "auditorium": 2},
            ttl_seconds=120,
        )

        assert await redis.hgetall("screening:10:details") == {
            "title": "Alien",
            "auditorium": "2",
        }
        assert await redis.ttl("screening:10:details") == 120

    run(scenario())


def test_clear_cache_by_prefix_deletes_matching_keys_in_batches():
    async def scenario():
        redis = FakeRedis()
        await redis.set("screening:10::A1", "user-1")
        await redis.set("screening:10:details", "cached")
        await redis.set("screening:11::A1", "user-1")

        deleted = await redis_seats.clear_cache_by_prefix(redis, "10", batch_size=1)

        assert deleted == 2
        assert await redis.get("screening:10::A1") is None
        assert await redis.get("screening:10:details") is None
        assert await redis.get("screening:11::A1") == "user-1"

    run(scenario())


def test_close_screening_sale_removes_cached_seat_state():
    async def scenario():
        redis = FakeRedis()
        await redis.hset("screening:10:seat_map", mapping={"A1": "available"})
        await redis.set("screening:10::A1", "user-1", ex=60)
        await redis.set("screening:11::A1", "user-1", ex=60)

        deleted = await redis_seats.close_screening_sale(redis, "10")

        assert deleted == 2
        assert await redis.hgetall("screening:10:seat_map") == {}
        assert await redis.get("screening:10::A1") is None
        assert await redis.get("screening:11::A1") == "user-1"

    run(scenario())


def test_clear_cache_by_prefix_requires_screening_id():
    async def scenario():
        redis = FakeRedis()

        with pytest.raises(ValueError, match="screening_id"):
            await redis_seats.clear_cache_by_prefix(redis, "")

    run(scenario())


def test_publish_seat_update_adds_stream_message():
    async def scenario():
        redis = FakeRedis()

        await redis_seats.publish_seat_update(redis, "10", "A1", "locked")

        assert redis.streams == {
            "stream:screening:10": [("1-0", {"seat_id": "A1", "status": "locked", "owner_tag": ""})]
        }

    run(scenario())


def test_expired_seat_listener_publishes_available_update_for_seat_keys():
    async def scenario():
        redis = FakeRedis()
        redis.pubsub_messages = [
            {"type": "subscribe", "data": "__keyevent@0__:expired"},
            {"type": "message", "data": "screening:10::A1"},
            {"type": "message", "data": "screening:10:seat_map"},
            {"type": "message", "data": "other:10::A2"},
        ]

        await redis_seats.listen_for_expired_seat_holds(redis)

        assert redis.streams == {
            "stream:screening:10": [
                ("1-0", {"seat_id": "A1", "status": "available", "owner_tag": ""})
            ]
        }
        assert redis.pubsub_instance.subscribed_channels == [
            "__keyevent@*__:expired"
        ]
        assert redis.pubsub_instance.unsubscribed_channels == [
            "__keyevent@*__:expired"
        ]
        assert redis.pubsub_instance.closed is True

    run(scenario())


def test_stream_sse_events_formats_first_stream_message():
    async def scenario():
        redis = FakeRedis()
        await redis.xadd("stream:screening:10", {"seat_id": "A1", "status": "locked"})

        stream = redis_seats.stream_sse_events(redis, "10")
        event = await anext(stream)
        await stream.aclose()

        assert event == (
            'id: 1-0\n'
            'event: seat_update\n'
            'data: {"id": "1-0", "seat_id": "A1", "status": "locked"}\n\n'
        )

    run(scenario())