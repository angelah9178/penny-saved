# A Penny Saved

A Penny Saved is a React and FastAPI application for tracking impulse purchases that were avoided or completed after a waiting period.

## Prerequisites

- Node.js 22 LTS (the exact project version is in `.nvmrc`)
- Python 3.12 or newer (the baseline is in `.python-version`)

## Install the scaffold

Install the frontend with the committed lockfile:

```bash
cd frontend
npm ci
```

Create a backend virtual environment and install the pinned development dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

## Baseline checks

Frontend commands are run from `frontend/`:

```bash
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

Backend commands are run from `backend/` with the virtual environment active:

```bash
ruff format --check .
ruff check .
pytest
```

Local environment, database, and combined development commands are added in DEV-002 and later foundation work.
