"""Shared authentication security primitives."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_PASSWORD_HASH = PasswordHash.recommended()
SESSION_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a plaintext password with the project's recommended algorithm."""
    return _PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a plaintext password matches a stored password hash."""
    try:
        return _PASSWORD_HASH.verify(password, password_hash)
    except UnknownHashError:
        return False


def verify_and_update_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Verify a password and return a replacement hash when parameters are outdated."""
    try:
        return _PASSWORD_HASH.verify_and_update(password, password_hash)
    except UnknownHashError:
        return False, None


def generate_session_token(
    token_factory: Callable[[int], str] = secrets.token_urlsafe,
) -> str:
    """Generate an opaque session token with a cryptographically secure default."""
    return token_factory(SESSION_TOKEN_BYTES)


def digest_session_token(raw_token: str) -> str:
    """Return the lowercase SHA-256 digest persisted for a raw session token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
