"""The Redis-to-SSE relay (SAAS §7.3) against a faked pub/sub client:
subscribe-before-enqueue ordering and stream_end termination."""

import json

import pytest

from backend.jobs import stream as stream_module
from backend.jobs.stream import job_event_stream


class FakePubSub:
    def __init__(self, messages):
        self._messages = list(messages)
        self.subscribed_to: list[str] = []
        self.closed = False

    async def subscribe(self, channel):
        self.subscribed_to.append(channel)

    async def get_message(self, ignore_subscribe_messages=True, **kwargs):  # matches redis-py
        if self._messages:
            item = self._messages.pop(0)
            if item is None:
                return None  # simulates a poll timeout tick
            return {"type": "message", "data": json.dumps(item)}
        return {"type": "message", "data": json.dumps({"type": "stream_end"})}

    async def aclose(self):
        self.closed = True


class FakeRedisClient:
    def __init__(self, pubsub):
        self._pubsub = pubsub
        self.closed = False

    def pubsub(self):
        return self._pubsub

    async def aclose(self):
        self.closed = True


@pytest.fixture
def fake_redis(monkeypatch):
    holder = {}

    def install(messages):
        pubsub = FakePubSub(messages)
        client = FakeRedisClient(pubsub)
        monkeypatch.setattr(stream_module.Redis, "from_url", staticmethod(lambda *a, **k: client))
        holder["pubsub"], holder["client"] = pubsub, client
        return holder

    return install


async def test_relay_subscribes_before_enqueueing(fake_redis):
    h = fake_redis([{"type": "start"}, {"type": "complete"}])
    order: list[str] = []

    async def enqueue():
        order.append("enqueue")
        # Subscription must already exist at this point.
        assert h["pubsub"].subscribed_to == ["job:r1"]

    events = [e async for e in job_event_stream("r1", enqueue=enqueue)]
    assert order == ["enqueue"]
    assert [e["type"] for e in events] == ["start", "complete"]  # stream_end consumed
    assert h["pubsub"].closed and h["client"].closed


async def test_relay_tolerates_idle_polls(fake_redis):
    fake_redis([None, {"type": "start"}, None, {"type": "error"}])
    events = [e async for e in job_event_stream("r2")]
    assert [e["type"] for e in events] == ["start", "error"]
