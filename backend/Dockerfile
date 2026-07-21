# Build context is the repo root (see docker-compose.yml)
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependency layer — cached unless the lockfile changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim-bookworm

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    # Containers ship logs to a collector, not a human tail — JSON by default.
    LOG_FORMAT=json

COPY backend ./backend

# Never run as root: a compromised app process shouldn't own the container.
RUN groupadd --system app && useradd --system --gid app --no-create-home app
USER app

EXPOSE 8000

# Readiness (includes a DB ping), not just liveness — an API that can't reach
# Postgres reports unhealthy and compose/orchestrators act on it.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4)"]

# Apply migrations, then serve
CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
