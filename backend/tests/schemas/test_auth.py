"""Tests for authentication API contracts."""

from __future__ import annotations

from uuid import UUID

import pytest
from app.schemas.auth import AuthRequest, AuthResponse, UserResponse, normalize_email
from pydantic import ValidationError


def test_auth_request_normalizes_email_without_changing_password() -> None:
    request = AuthRequest(email="  Person@Example.COM  ", password="  password  ")

    assert request.email == "person@example.com"
    assert request.password.get_secret_value() == "  password  "


@pytest.mark.parametrize("email", ["missing-at.example.com", "@example.com", "user@", "a @b.com"])
def test_auth_request_rejects_invalid_email(email: str) -> None:
    with pytest.raises(ValidationError):
        AuthRequest(email=email, password="password123")


@pytest.mark.parametrize("length", [7, 129])
def test_auth_request_rejects_password_outside_bounds(length: int) -> None:
    with pytest.raises(ValidationError):
        AuthRequest(email="user@example.com", password="x" * length)


@pytest.mark.parametrize("length", [8, 128])
def test_auth_request_accepts_password_boundaries(length: int) -> None:
    request = AuthRequest(email="user@example.com", password="x" * length)

    assert len(request.password.get_secret_value()) == length


def test_auth_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AuthRequest.model_validate(
            {
                "email": "user@example.com",
                "password": "password123",
                "is_admin": True,
            }
        )


def test_password_is_redacted_from_schema_output_and_errors() -> None:
    plaintext = "unique-plaintext-password"
    request = AuthRequest(email="user@example.com", password=plaintext)

    assert plaintext not in repr(request)
    assert plaintext not in request.model_dump_json()

    with pytest.raises(ValidationError) as error:
        AuthRequest(email="user@example.com", password=plaintext * 20)
    assert plaintext not in str(error.value)


def test_auth_response_contains_only_public_user_fields() -> None:
    response = AuthResponse(
        user=UserResponse(
            id=UUID("11111111-1111-4111-8111-111111111111"),
            email="user@example.com",
        )
    )

    assert response.model_dump(mode="json") == {
        "user": {
            "id": "11111111-1111-4111-8111-111111111111",
            "email": "user@example.com",
        }
    }


def test_normalize_email_is_shared_and_predictable() -> None:
    assert normalize_email("\tUSER@Example.COM\n") == "user@example.com"
