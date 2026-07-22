"""Shared test configuration loaded before application modules are imported."""

import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://penny_saved_test:test-only@localhost:5432/penny_saved_test",
)
os.environ.setdefault("FRONTEND_ORIGIN", "http://testserver")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
