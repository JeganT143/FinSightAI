"""Relay a queued job's Redis pub/sub events to an SSE consumer (SAAS §7.3).

Subscribe-then-enqueue ordering matters: the subscription must exist before
the worker can publish, or the first events are lost. Callers pass the
enqueue step as a callback so this module owns that ordering.

Known gap, on purpose: reconnecting mid-run misses events published while
disconnected (no replay buffer). The terminal state is never lost — the
jobs stream endpoint serves a DB snapshot for finished reports — and a
replay log (Redis Streams instead of pub/sub) is the noted upgrade path.
"""

import json
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable

from redis.asyncio import Redis

from backend.core.config import settings
from backend.jobs.research_job import job_channel

logger = logging.getLogger(__name__)

_STREAM_DEADLINE_SECONDS = 900  # matches the worker's job_timeout
_POLL_SECONDS = 5.0


async def job_event_stream(
    report_id: str, enqueue: Callable[[], Awaitable[None]] | None = None
) -> AsyncGenerator[dict]:
    """Yield job events for `report_id` until the worker signals stream_end."""
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    deadline = time.monotonic() + _STREAM_DEADLINE_SECONDS
    try:
        await pubsub.subscribe(job_channel(report_id))
        if enqueue is not None:
            await enqueue()
        while time.monotonic() < deadline:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=_POLL_SECONDS
            )
            if message is None:
                continue
            event = json.loads(message["data"])
            if event.get("type") == "stream_end":
                return
            yield event
        logger.warning(
            "job stream for %s hit the %ds deadline", report_id, _STREAM_DEADLINE_SECONDS
        )
    finally:
        await pubsub.aclose()
        await client.aclose()
