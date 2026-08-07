from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.auth_claims import VerifiedAccessTokenClaims
from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, password_hash_value: str) -> bool:
    return password_hash.verify(plain_password, password_hash_value)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": expires_at,
        "jti": str(uuid4()),
        "iss": settings.jwt_issuer,
        "aud": list(settings.jwt_audiences),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_verified_access_token(token: str) -> VerifiedAccessTokenClaims | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audiences,
            issuer=settings.jwt_issuer,
            leeway=0,
            options={"require": ["sub", "iat", "exp", "jti", "iss", "aud"]},
        )
        if set(payload) != {"sub", "iat", "exp", "jti", "iss", "aud"}:
            return None
        subject, jti, issuer = payload["sub"], payload["jti"], payload["iss"]
        issued_at, expires_at, audience = payload["iat"], payload["exp"], payload["aud"]
        if (
            not isinstance(subject, str)
            or not subject
            or subject != subject.strip()
            or not isinstance(jti, str)
            or not jti
            or jti != jti.strip()
            or not isinstance(issuer, str)
            or issuer != settings.jwt_issuer
            or isinstance(issued_at, bool)
            or not isinstance(issued_at, int)
            or isinstance(expires_at, bool)
            or not isinstance(expires_at, int)
            or expires_at <= issued_at
        ):
            return None
        if isinstance(audience, str):
            audiences = (audience,)
        elif isinstance(audience, list) and all(isinstance(item, str) for item in audience):
            audiences = tuple(audience)
        else:
            return None
        if (
            not 1 <= len(audiences) <= 8
            or len(set(audiences)) != len(audiences)
            or any(not item or item != item.strip() or len(item) > 200 for item in audiences)
            or not set(audiences).intersection(settings.jwt_audiences)
        ):
            return None
        return VerifiedAccessTokenClaims(
            subject=subject,
            jti_reference=jti,
            verified_issuer=issuer,
            verified_audiences=audiences,
            issued_at=datetime.fromtimestamp(issued_at, UTC),
            expires_at=datetime.fromtimestamp(expires_at, UTC),
        )
    except (InvalidTokenError, TypeError, ValueError, OverflowError):
        return None


def decode_access_token(token: str) -> dict[str, Any] | None:
    claims = decode_verified_access_token(token)
    if claims is None:
        return None
    return {
        "sub": claims.subject,
        "iat": int(claims.issued_at.timestamp()),
        "exp": int(claims.expires_at.timestamp()),
        "jti": claims.jti_reference,
        "iss": claims.verified_issuer,
        "aud": list(claims.verified_audiences),
    }
