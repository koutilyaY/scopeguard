SHELL := /bin/bash
COMPOSE := docker compose
COMPOSE_DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml
API_DIR := apps/api
WEB_DIR := apps/web
VENV := $(API_DIR)/.venv
PY := $(VENV)/bin/python

.PHONY: setup dev dev-api dev-web dev-worker up down logs migrate seed \
        test test-unit test-integration test-e2e lint typecheck format \
        eval eval-ollama clean backup restore

## ---- setup ----------------------------------------------------------------

setup: ## install backend venv + frontend deps, copy .env
	@test -f .env || cp .env.example .env
	python3.12 -m venv $(VENV) || python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip -q
	$(VENV)/bin/pip install -e "$(API_DIR)[dev]" -q
	cd $(WEB_DIR) && npm install

## ---- run ------------------------------------------------------------------

up: ## full stack via docker
	$(COMPOSE) up --build -d
	@echo "web:     http://localhost:3000"
	@echo "api:     http://localhost:8000/docs"
	@echo "minio:   http://localhost:9003"
	@echo "mailpit: http://localhost:8025"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

dev: ## start infra containers only (hot-reload servers run on host)
	$(COMPOSE_DEV) up -d postgres redis minio mailpit
	@echo "Now run 'make dev-api', 'make dev-worker' and 'make dev-web' in separate terminals."

dev-api:
	cd $(API_DIR) && DATABASE_URL=postgresql+psycopg://scopeguard:scopeguard-dev-password@localhost:5433/scopeguard \
	  REDIS_URL=redis://localhost:6380/0 CELERY_BROKER_URL=redis://localhost:6380/1 \
	  CELERY_RESULT_BACKEND=redis://localhost:6380/2 MINIO_ENDPOINT=localhost:9002 \
	  .venv/bin/uvicorn app.main:app --reload --port 8000

dev-worker:
	cd $(API_DIR) && DATABASE_URL=postgresql+psycopg://scopeguard:scopeguard-dev-password@localhost:5433/scopeguard \
	  REDIS_URL=redis://localhost:6380/0 CELERY_BROKER_URL=redis://localhost:6380/1 \
	  CELERY_RESULT_BACKEND=redis://localhost:6380/2 MINIO_ENDPOINT=localhost:9002 \
	  .venv/bin/celery -A app.worker.celery_app worker --loglevel=INFO

dev-web:
	cd $(WEB_DIR) && npm run dev

migrate: ## run alembic migrations inside compose api container (or host in dev)
	$(COMPOSE) run --rm api alembic upgrade head

seed: ## load the Northstar demo organization
	$(COMPOSE) run --rm api python -m app.seed

## ---- quality --------------------------------------------------------------

test: test-unit test-integration
	cd $(WEB_DIR) && npm run test -- --run

test-unit:
	cd $(API_DIR) && .venv/bin/pytest tests/unit -q

test-integration:
	cd $(API_DIR) && .venv/bin/pytest tests/integration tests/security -q

test-e2e:
	cd $(WEB_DIR) && npx playwright test

lint:
	cd $(API_DIR) && .venv/bin/ruff check app tests
	cd $(WEB_DIR) && npm run lint

typecheck:
	cd $(API_DIR) && .venv/bin/mypy app
	cd $(WEB_DIR) && npm run typecheck

format:
	cd $(API_DIR) && .venv/bin/ruff format app tests && .venv/bin/ruff check --fix app tests
	cd $(WEB_DIR) && npm run format

## ---- evaluation -----------------------------------------------------------

eval: ## deterministic evaluation suite (fake provider — must be 100% on financials)
	cd $(API_DIR) && LLM_PROVIDER=fake .venv/bin/python -m evaluations.run --provider fake

eval-ollama: ## optional: evaluate against a live local Ollama model
	cd $(API_DIR) && LLM_PROVIDER=ollama OLLAMA_BASE_URL=$${OLLAMA_BASE_URL:-http://localhost:11434} \
	  .venv/bin/python -m evaluations.run --provider ollama

## ---- ops ------------------------------------------------------------------

backup: ## dump postgres + minio into ./backups/<timestamp>
	./scripts/backup.sh

restore: ## restore from a backup directory: make restore FROM=backups/<timestamp>
	./scripts/restore.sh $(FROM)

clean:
	$(COMPOSE) down -v --remove-orphans
	rm -rf $(API_DIR)/.pytest_cache $(API_DIR)/.mypy_cache $(API_DIR)/.ruff_cache \
	       $(WEB_DIR)/.next $(WEB_DIR)/test-results $(WEB_DIR)/playwright-report
