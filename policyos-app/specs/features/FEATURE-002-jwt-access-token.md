# FEATURE-002 ??JWT Access Token

## Configuration
- `secret_key`: unique and at least 32 bytes outside local development and tests
- `jwt_algorithm`: defaults to `HS256`
- `access_token_expire_minutes`: defaults to 30

## Implemented requirements
- token includes only `sub`, `iat`, `exp`, and `jti`
- expiration is configurable
- decoding requires every claim and rejects invalid signatures and expired tokens
- the subject is parsed as a user UUID by `get_current_user`
- memberships and permissions are never embedded in the token

## Out of scope
Refresh tokens, logout, and server-side revocation are deferred as recorded in `specs/decisions/ADR-003-jwt.md`.
