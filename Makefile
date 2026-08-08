.DEFAULT_GOAL := help

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON ?= python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
BACKEND_PYTHON := $(abspath $(VENV_PYTHON))
ALEMBIC := ../$(VENV)/bin/python -m alembic
LOCAL_DB_GUARD := ./scripts/require-local-database.sh
POSTGRES_VOLUME := penny_saved_postgres_data

.PHONY: help env-setup install frontend-install backend-install \
	frontend-format backend-format format \
	frontend-format-check backend-format-check format-check \
	frontend-lint backend-lint lint \
	frontend-typecheck typecheck \
	frontend-test backend-test test \
	frontend-build backend-build build check clean \
	operations-check \
	frontend-security-check backend-security-check security-check \
	frontend-dev backend-dev dev \
	db-up db-down db-logs db-reset db-upgrade db-downgrade db-revision seed-demo \
	check-frontend check-backend check-backend-env check-docker check-alembic

help: ## List available development commands.
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

env-setup: ## Copy missing local environment files from committed examples.
	@for pair in ".env.example:.env" "backend/.env.example:backend/.env" "frontend/.env.example:frontend/.env"; do \
		source_file="$${pair%%:*}"; destination="$${pair##*:}"; \
		if [[ -e "$$destination" ]]; then \
			echo "Keeping existing $$destination"; \
		else \
			cp "$$source_file" "$$destination"; \
			echo "Created $$destination; review placeholder values before use."; \
		fi; \
	done

install: backend-install frontend-install ## Install backend and frontend dependencies.

frontend-install: ## Install frontend dependencies from package-lock.json.
	@command -v node >/dev/null || { echo "Node.js 22 is required. See .nvmrc." >&2; exit 1; }
	@command -v npm >/dev/null || { echo "npm is required." >&2; exit 1; }
	@node_major=$$(node --version | sed 's/^v//' | cut -d. -f1); \
		[[ "$$node_major" == "22" ]] || { echo "Node.js 22 is required; found $$(node --version)." >&2; exit 1; }
	npm --prefix frontend ci

backend-install: ## Create .venv and install pinned backend development dependencies.
	@command -v $(PYTHON) >/dev/null || { echo "Python 3.12 or newer is required." >&2; exit 1; }
	@$(PYTHON) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else "Python 3.12 or newer is required")'
	@test -x $(VENV_PYTHON) || $(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r backend/requirements-dev.txt

check-frontend:
	@command -v node >/dev/null || { echo "Node.js 22 is required. See .nvmrc." >&2; exit 1; }
	@command -v npm >/dev/null || { echo "npm is required." >&2; exit 1; }
	@test -d frontend/node_modules || { echo "Missing frontend dependencies. Run 'make frontend-install'." >&2; exit 1; }

check-backend:
	@test -x $(VENV_PYTHON) || { echo "Missing .venv. Run 'make backend-install'." >&2; exit 1; }

check-backend-env: check-backend
	@test -f backend/.env || { echo "Missing backend/.env. Run 'make env-setup' and review its values." >&2; exit 1; }

frontend-format: check-frontend ## Format frontend files with Prettier.
	npm --prefix frontend run format

backend-format: check-backend ## Format backend files with Ruff.
	cd backend && $(BACKEND_PYTHON) -m ruff format .

format: ## Format frontend and backend files.
	$(MAKE) frontend-format
	$(MAKE) backend-format

frontend-format-check: check-frontend ## Check frontend formatting with Prettier.
	npm --prefix frontend run format:check

backend-format-check: check-backend ## Check backend formatting with Ruff.
	cd backend && $(BACKEND_PYTHON) -m ruff format --check .

format-check: ## Check frontend and backend formatting.
	$(MAKE) frontend-format-check
	$(MAKE) backend-format-check

frontend-lint: check-frontend ## Lint frontend files with ESLint.
	npm --prefix frontend run lint

backend-lint: check-backend ## Lint backend files with Ruff.
	cd backend && $(BACKEND_PYTHON) -m ruff check .

lint: ## Lint frontend and backend files.
	$(MAKE) frontend-lint
	$(MAKE) backend-lint

frontend-typecheck: check-frontend ## Type-check the frontend with TypeScript.
	npm --prefix frontend run typecheck

typecheck: ## Run configured static type checks.
	$(MAKE) frontend-typecheck

frontend-test: check-frontend ## Run the frontend test suite once.
	npm --prefix frontend test

backend-test: check-backend-env ## Run the backend test suite against the configured test database.
	cd backend && set -a && source .env && set +a && \
		[[ -n "$${TEST_DATABASE_URL:-}" ]] || { \
			echo "Missing TEST_DATABASE_URL in backend/.env. Configure the dedicated PostgreSQL test database." >&2; \
			exit 1; \
		}; \
		$(BACKEND_PYTHON) -m pytest

test: ## Run frontend and backend test suites.
	$(MAKE) frontend-test
	$(MAKE) backend-test

frontend-build: check-frontend ## Build the production frontend.
	npm --prefix frontend run build

backend-build: check-backend ## Validate backend application construction with safe test settings.
	cd backend && APP_ENV=test \
		DATABASE_URL=postgresql+psycopg://quality_check:quality_check@localhost/quality_check \
		$(BACKEND_PYTHON) -c 'from app.main import create_app; create_app()'

build: ## Build the frontend and validate backend application construction.
	$(MAKE) frontend-build
	$(MAKE) backend-build

check: ## Run all frontend and backend quality checks.
	$(MAKE) format-check
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) build
	$(MAKE) operations-check

operations-check: check-backend ## Validate secret-free production operations examples.
	$(VENV_PYTHON) scripts/check_operations.py

frontend-security-check: check-frontend ## Audit the locked frontend dependency graph for high-severity advisories.
	node scripts/audit-frontend.mjs

backend-security-check: check-backend ## Audit pinned backend runtime dependencies for known advisories.
	$(VENV_PYTHON) -m pip_audit --requirement backend/requirements.txt --progress-spinner off

security-check: ## Run frontend and backend dependency vulnerability scans.
	$(MAKE) frontend-security-check
	$(MAKE) backend-security-check

clean: ## Remove generated build, coverage, bytecode, and tool-cache artifacts only.
	./scripts/clean-generated.sh

frontend-dev: check-frontend ## Start the Vite frontend development server.
	npm --prefix frontend run dev

backend-dev: check-backend-env ## Start the FastAPI backend development server.
	cd backend && $(BACKEND_PYTHON) -m uvicorn app.main:create_app \
		--factory --reload --host 127.0.0.1 --port 8000

dev: check-frontend check-backend-env check-docker check-alembic ## Start PostgreSQL, migrations, frontend, and backend.
	$(MAKE) db-up
	$(MAKE) db-upgrade
	./scripts/run-dev.sh

check-docker:
	@command -v docker >/dev/null || { echo "Docker Engine with Compose v2 is required." >&2; exit 1; }
	@docker compose version >/dev/null || { echo "Docker Compose v2 is required ('docker compose')." >&2; exit 1; }
	@test -f .env || { echo "Missing .env. Run 'make env-setup' and review its values." >&2; exit 1; }

db-up: check-docker ## Start PostgreSQL and wait until it is healthy.
	docker compose up --detach --wait --wait-timeout 60 postgres

db-down: check-docker ## Stop PostgreSQL without deleting its named volume.
	docker compose down

db-logs: check-docker ## Follow PostgreSQL logs.
	docker compose logs --follow postgres

db-reset: check-docker ## Delete and recreate only the local PostgreSQL data volume.
	@if [[ -n "$${CI:-}" ]]; then echo "Refusing db-reset in CI." >&2; exit 1; fi
	@$(LOCAL_DB_GUARD) "database reset"
	@read -r -p "Delete local volume '$(POSTGRES_VOLUME)' and all its data? Type 'reset': " answer; \
		[[ "$$answer" == "reset" ]] || { echo "Reset cancelled."; exit 1; }
	docker compose down
	docker volume rm $(POSTGRES_VOLUME)
	$(MAKE) db-up

check-alembic:
	@test -x $(VENV_PYTHON) || { echo "Missing .venv. Run 'make backend-install'." >&2; exit 1; }
	@test -f backend/.env || { echo "Missing backend/.env. Run 'make env-setup' and review its values." >&2; exit 1; }
	@test -f backend/alembic.ini || { echo "Alembic configuration is added by DEV-005; database migrations are not available yet." >&2; exit 1; }

db-upgrade: check-alembic ## Apply all pending database migrations.
	cd backend && $(ALEMBIC) upgrade head

db-downgrade: check-alembic ## Revert one migration on a confirmed local development database.
	@$(LOCAL_DB_GUARD) "database downgrade"
	@read -r -p "Downgrade the local development database by one revision? Type 'downgrade': " answer; \
		[[ "$$answer" == "downgrade" ]] || { echo "Downgrade cancelled."; exit 1; }
	cd backend && $(ALEMBIC) downgrade -1

db-revision: check-alembic ## Create a reviewed migration: make db-revision message="description".
	@$(LOCAL_DB_GUARD) "migration revision creation"
	@test -n "$(message)" || { echo "Usage: make db-revision message=\"describe_change\"" >&2; exit 1; }
	cd backend && $(ALEMBIC) revision --autogenerate -m "$(message)"

seed-demo: check-alembic ## Seed guarded deterministic data into an already migrated local database.
	cd backend && $(BACKEND_PYTHON) -m app.scripts.seed_demo
