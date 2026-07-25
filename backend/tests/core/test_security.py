"""Tests for shared authentication security primitives."""

from __future__ import annotations

import hashlib

from app.core.security import (
    SESSION_TOKEN_BYTES,
    digest_session_token,
    generate_session_token,
    hash_password,
    is_valid_session_token,
    verify_and_update_password,
    verify_password,
)
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher


def test_password_hash_round_trip_does_not_contain_plaintext() -> None:
    password = "correct horse battery staple"

    password_hash = hash_password(password)

    assert password not in password_hash
    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)


def test_malformed_password_hash_is_rejected_safely() -> None:
    assert not verify_password("password123", "not-a-password-hash")
    assert verify_and_update_password("password123", "not-a-password-hash") == (False, None)


def test_current_password_hash_does_not_need_replacement() -> None:
    password = "password123"
    password_hash = hash_password(password)

    valid, replacement_hash = verify_and_update_password(password, password_hash)

    assert valid
    assert replacement_hash is None


def test_outdated_password_hash_is_replaced_after_successful_verification() -> None:
    password = "password123"
    outdated_hasher = PasswordHash(
        (
            Argon2Hasher(
                time_cost=1,
                memory_cost=8_192,
                parallelism=1,
            ),
        )
    )
    outdated_hash = outdated_hasher.hash(password)

    valid, replacement_hash = verify_and_update_password(password, outdated_hash)

    assert valid
    assert replacement_hash is not None
    assert replacement_hash != outdated_hash
    assert verify_password(password, replacement_hash)


def test_session_token_uses_32_byte_secure_factory_contract() -> None:
    requested_sizes: list[int] = []

    def token_factory(size: int) -> str:
        requested_sizes.append(size)
        return "deterministic-opaque-token"

    assert generate_session_token(token_factory) == "deterministic-opaque-token"
    assert requested_sizes == [SESSION_TOKEN_BYTES]


def test_default_session_tokens_are_opaque_and_distinct() -> None:
    first = generate_session_token()
    second = generate_session_token()

    assert len(first) >= 43
    assert first != second
    assert first.isascii()
    assert second.isascii()


def test_session_token_digest_is_deterministic_lowercase_sha256() -> None:
    raw_token = "browser-only-token"
    expected = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    digest = digest_session_token(raw_token)

    assert digest == expected
    assert len(digest) == 64
    assert digest == digest.lower()
    assert raw_token not in digest


def test_generated_session_token_has_the_accepted_cookie_shape() -> None:
    assert is_valid_session_token(generate_session_token())


def test_missing_or_malformed_session_tokens_are_rejected() -> None:
    assert not is_valid_session_token(None)
    assert not is_valid_session_token("")
    assert not is_valid_session_token("too-short")
    assert not is_valid_session_token("x" * 42)
    assert not is_valid_session_token("x" * 44)
    assert not is_valid_session_token("x" * 42 + "!")
