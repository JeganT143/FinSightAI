"""Arq worker process (SAAS §7.1). Run as: arq backend.worker.WorkerSettings

Same Docker image as the API, different command — one artifact, two process
types (the compose `worker` service / the Container Apps worker app).
"""

from typing import Any

from arq.connections import RedisSettings
from dotenv import load_dotenv

load_dotenv()

from backend.core.config import settings  # noqa: E402
from backend.core.logging import configure_logging  # noqa: E402
from backend.jobs.research_job import run_research_job  # noqa: E402

configure_logging(settings.log_level, settings.log_format)


async def on_startup(ctx: dict[str, Any]) -> None:
    import logging

    logging.getLogger(__name__).info(
        "worker up: max_jobs=%d timeout=%ds", settings.max_concurrent_runs, 900
    )


class WorkerSettings:
    functions = [run_research_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # The worker owns run concurrency in queued mode (the API's RunGate only
    # guards inline execution) — same knob, same meaning.
    max_jobs = settings.max_concurrent_runs
    job_timeout = 900  # hard stop well above agent_timeout_seconds * phases
    on_startup = on_startup
