# FinSightAI developer entry points. Every CI check has a target here, so
# "works locally" and "works in CI" are the same commands.

.DEFAULT_GOAL := help

.PHONY: help setup db migrate api web test cov evals-llm lint format typecheck check up down

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend (uv) and frontend (npm) dependencies
	uv sync
	cd frontend/web && npm ci

db: ## Start Postgres (pgvector) via docker compose
	docker compose up -d db

migrate: db ## Apply Alembic migrations to the running database
	uv run alembic -c backend/alembic.ini upgrade head

api: ## Run the FastAPI backend with reload (expects db up + migrated)
	uv run uvicorn backend.main:app --reload --port 8000

web: ## Run the Next.js frontend dev server
	cd frontend/web && npm run dev

test: ## Unit tests + deterministic evals (no LLM calls, no network)
	uv run pytest tests evals -q

cov: ## Tests with the same coverage gate CI enforces
	uv run pytest tests evals -q --cov=backend --cov-report=term-missing --cov-fail-under=80

evals-llm: ## LLM-as-judge evals (calls OpenAI; costs money)
	uv run pytest evals -m llm_eval -q

lint: ## Ruff lint + format check
	uv run ruff check backend tests evals
	uv run ruff format --check backend tests evals

format: ## Auto-format and auto-fix
	uv run ruff format backend tests evals
	uv run ruff check --fix backend tests evals

typecheck: ## mypy over the backend
	uv run mypy backend

check: lint typecheck test ## Everything CI's backend job runs

up: ## Full dockerized stack (db + backend + frontend)
	docker compose --profile full up --build

down: ## Stop the stack
	docker compose --profile full down
