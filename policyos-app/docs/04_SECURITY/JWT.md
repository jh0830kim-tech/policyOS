# JWT Policy

## Implemented claims
Sprint 2 access tokens contain only:
- `sub`: user UUID as a string
- `iat`: issued-at time
- `exp`: expiration time
- `jti`: unique token identifier

Tokens do not contain email addresses, password data, memberships, roles, or permission lists. Current user, membership, and permission state is resolved from trusted database storage on each protected request.

## Validation and response rules
- Sign and verify using the configured algorithm and `SECRET_KEY`.
- Require `sub`, `iat`, `exp`, and `jti` during decoding.
- Reject malformed, expired, incorrectly signed, missing-claim, and invalid-subject tokens.
- Return the same generic `401` response with `WWW-Authenticate: Bearer` for token failures.
- Keep the default access-token lifetime short; it is currently 30 minutes and configurable with `ACCESS_TOKEN_EXPIRE_MINUTES`.

## Secret requirements
Local development uses an explicit non-production default. Any environment other than development, local, or test rejects secrets shorter than 32 bytes and rejects known development or example placeholders. Generate a unique cryptographically random `SECRET_KEY` for each deployment as described in `.env.example`.

## Deferred lifecycle work
Refresh tokens and server-side revocation are not implemented because the MVP has no token persistence or revocation store. Clients discard access tokens locally, and tokens expire after their short lifetime. See `specs/decisions/ADR-003-jwt.md`.
