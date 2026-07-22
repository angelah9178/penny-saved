.DEFAULT_GOAL := help

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON ?= python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
ALEMBIC := ../$(VENV)/bin/python -m alembic
LOCAL_DB_GUARD := ./scripts/require-local-database.sh
POSTGRES_VOLUME := penny_saved_postgres_data

.PHONY: help env-setup install frontend-install backend-install db-up db-down db-logs db-reset db-upgrade db-downgrade db-revision check-docker check-alembic

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
