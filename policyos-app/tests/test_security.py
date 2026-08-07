import datetime as dt
from datetime import timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.core.auth_claims import VerifiedAccessTokenClaims
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    decode_verified_access_token,
    hash_password,
    verify_password,
)


def test_correct_password_verifies() -> None:
    password = "correct horse battery staple"
    password_hash = hash_password(password)
    assert password_hash != password
    assert verify_password(password, password_hash)


def test_incorrect_password_does_not_verify() -> None:
    password_hash = hash_password("correct password")
    assert not verify_password("incorrect password", password_hash)


def test_password_hashes_use_unique_salts() -> None:
    password = "same password"
    assert hash_password(password) != hash_password(password)


def test_valid_access_token_contains_required_claims() -> None:
    payload = decode_access_token(create_access_token("user-123"))
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert set(payload) == {"sub", "iat", "exp", "jti", "iss", "aud"}


def test_access_token_with_invalid_signature_is_rejected() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "user-123", "iat": 1, "exp": 4_102_444_800, "jti": "token-id"},
        "different-secret-that-is-at-least-32-bytes",
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(token) is None


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token("user-123", expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


def _encode_claims(**overrides: object) -> str:
    settings = get_settings()
    now = dt.datetime.now(dt.UTC)
    payload: dict[str, object] = {
        "sub": "user-123",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "jti": "token-id",
        "iss": settings.jwt_issuer,
        "aud": list(settings.jwt_audiences),
    }
    payload.update(overrides)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _encode_without(claim: str) -> str:
    settings = get_settings()
    payload = jwt.decode(
        _encode_claims(),
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"verify_aud": False},
    )
    payload.pop(claim)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def test_issued_token_has_trust_claims_and_typed_immutable_result() -> None:
    token = create_access_token("user-123")
    payload = decode_access_token(token)
    claims = decode_verified_access_token(token)
    settings = get_settings()

    assert payload is not None
    assert claims is not None
    assert isinstance(claims, VerifiedAccessTokenClaims)
    assert payload["iss"] == settings.jwt_issuer
    assert tuple(payload["aud"]) == settings.jwt_audiences
    assert claims.subject == "user-123"
    assert claims.verified_issuer == settings.jwt_issuer
    assert claims.verified_audiences == settings.jwt_audiences
    assert set(type(claims).model_fields) == {
        "subject",
        "jti_reference",
        "verified_issuer",
        "verified_audiences",
        "issued_at",
        "expires_at",
    }
    assert token not in repr(claims)
    assert settings.secret_key not in repr(claims)
    with pytest.raises(ValidationError):
        claims.subject = "different-user"


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("sub", ""),
        ("sub", 7),
        ("jti", ""),
        ("jti", 7),
        ("iss", ""),
    ],
)
def test_reference_claims_require_non_empty_exact_strings(claim: str, value: object) -> None:
    assert decode_verified_access_token(_encode_claims(**{claim: value})) is None


def test_non_string_issuer_returned_by_jwt_decoder_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = jwt.decode(
        _encode_claims(),
        options={"verify_signature": False},
    )
    payload["iss"] = 7

    def fake_decode(*args: object, **kwargs: object) -> dict[str, object]:
        return payload

    monkeypatch.setattr(jwt, "decode", fake_decode)

    assert decode_verified_access_token("typed-validation-test-token") is None


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("iat", True),
        ("iat", "1"),
        ("exp", True),
        ("exp", "4102444800"),
    ],
)
def test_numeric_claims_require_non_bool_exact_integers(claim: str, value: object) -> None:
    assert decode_verified_access_token(_encode_claims(**{claim: value})) is None


def test_issuer_and_audience_mismatch_are_rejected() -> None:
    assert (
        decode_verified_access_token(_encode_claims(iss="https://unknown-issuer.policyos.test"))
        is None
    )
    assert decode_verified_access_token(_encode_claims(aud=["unknown-audience"])) is None


@pytest.mark.parametrize("claim", ["iss", "aud"])
def test_missing_trust_claims_are_rejected(claim: str) -> None:
    assert decode_verified_access_token(_encode_without(claim)) is None


def test_legacy_four_claim_token_is_rejected() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "user-123", "iat": 1, "exp": 4_102_444_800, "jti": "legacy-id"},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert decode_verified_access_token(token) is None


def test_malformed_token_is_rejected() -> None:
    assert decode_verified_access_token("not-a-jwt") is None


@pytest.mark.parametrize(
    "audience",
    [
        "policyos-api-test",
        ["policyos-api-test"],
    ],
)
def test_audience_accepts_configured_string_or_string_array(audience: object) -> None:
    claims = decode_verified_access_token(_encode_claims(aud=audience))
    assert claims is not None
    assert claims.verified_audiences == ("policyos-api-test",)


@pytest.mark.parametrize(
    "audience",
    [
        "",
        [],
        [" policyos-api-test"],
        ["policyos-api-test", "policyos-api-test"],
        ["unknown-audience"],
    ],
)
def test_invalid_audience_values_are_rejected(audience: object) -> None:
    assert decode_verified_access_token(_encode_claims(aud=audience)) is None


def test_zero_leeway_rejects_token_expired_by_one_second() -> None:
    now = int(dt.datetime.now(dt.UTC).timestamp())
    token = _encode_claims(iat=now - 60, exp=now - 1)
    assert decode_verified_access_token(token) is None


def test_public_decode_access_token_dict_or_none_compatibility() -> None:
    payload = decode_access_token(create_access_token("user-123"))
    assert isinstance(payload, dict)
    assert payload["sub"] == "user-123"
    assert decode_access_token("not-a-jwt") is None
