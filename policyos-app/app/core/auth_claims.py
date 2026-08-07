"""Immutable verified access-token claims independent of Runtime services."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VerifiedAccessTokenClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    subject: str = Field(min_length=1, max_length=200)
    jti_reference: str = Field(min_length=1, max_length=200)
    verified_issuer: str = Field(min_length=1, max_length=200)
    verified_audiences: tuple[str, ...] = Field(min_length=1, max_length=8)
    issued_at: datetime
    expires_at: datetime

    @field_validator("subject", "jti_reference", "verified_issuer")
    @classmethod
    def trimmed_reference(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("verified token references must not have surrounding whitespace")
        return value

    @field_validator("verified_audiences")
    @classmethod
    def bounded_audiences(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("verified audiences must not contain duplicates")
        if any(not item or item != item.strip() or len(item) > 200 for item in value):
            raise ValueError("verified audiences must be non-empty, bounded, and trimmed")
        return value

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("verified token times must be timezone-aware")
        return value

    @model_validator(mode="after")
    def positive_lifetime(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("verified token must expire after issuance")
        return self


__all__ = ("VerifiedAccessTokenClaims",)
