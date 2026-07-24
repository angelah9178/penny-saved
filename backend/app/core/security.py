"""Shared password hashing primitives."""

from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_PASSWORD_HASH = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plaintext password with the project's recommended algorithm."""
    return _PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a plaintext password matches a stored password hash."""
    try:
        return _PASSWORD_HASH.verify(password, password_hash)
    except UnknownHashError:
        return False
