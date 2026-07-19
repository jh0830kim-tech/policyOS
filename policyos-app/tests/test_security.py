from datetime import timedelta

import jwt

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
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
    assert set(payload) == {"sub", "iat", "exp", "jti"}


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
