"""Application logging (ADR-12): stdlib logging, JSON output in production.

Why stdlib and not structlog/loguru: the whole requirement is "leveled logs,
one line per event, request ID attached, JSON when a collector is reading
them" — that is ~60 lines of stdlib. A logging framework is a dependency to
justify in every interview answer; this file is self-explanatory.

The request ID lives in a ContextVar so it survives async hops (every log
line emitted anywhere inside a request — pipeline, RAG, CRUD — carries the
same ID without threading it through call signatures).
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Stamp every record with the current request ID (or '-' outside a request)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line — what log collectors (CloudWatch, Loki) expect."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Install a single stdout handler on the root logger.

    Idempotent (replaces handlers rather than appending), so repeated app
    imports in tests don't multiply log lines.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s")
        )

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())

    # Route uvicorn's error log through our handler for a uniform format, and
    # silence its access log — RequestContextMiddleware emits a richer access
    # line (with request ID and duration) for every request.
    for name in ("uvicorn", "uvicorn.error"):
        upstream = logging.getLogger(name)
        upstream.handlers[:] = []
        upstream.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers[:] = []
    access.propagate = False
