"""Authentication request and response contracts."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 320


def normalize_email(email: str) -> str:
    """Normalize an account email consistently for persistence and lookup."""
    return email.strip().lower()


def _is_valid_email(email: str) -> bool:
    if any(character.isspace() for character in email):
        return False
    local_part, separator, domain = email.partition("@")
    return bool(local_part and separator and domain and "@" not in domain)


class AuthRequest(BaseModel):
    """Credentials accepted by signup and login."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: SecretStr = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
    )

    @field_validator("email")
    @classmethod
    def normalize_and_validate_email(cls, email: str) -> str:
        """Strip and lowercase an email, then reject malformed account identifiers."""
        normalized = normalize_email(email)
        if not _is_valid_email(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class UserResponse(BaseModel):
    """Public account fields safe to return to a client."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    email: str


class AuthResponse(BaseModel):
    """Envelope returned after successful authentication."""

    model_config = ConfigDict(extra="forbid")

    user: UserResponse
