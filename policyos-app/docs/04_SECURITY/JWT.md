# JWT Policy

## Implemented claims
Access tokens require:
- `sub`: user UUID as a string
- `iat`: issued-at time
- `exp`: expiration time
- `jti`: unique token identifier
- `iss`: exact configured `JWT_ISSUER`
- `aud`: one or more values checked against the configured `JWT_AUDIENCES` allowlist

Tokens do not contain email addresses, password data, memberships, roles, or permission lists. Current user, membership, and permission state is resolved from trusted database storage on each protected request.

## Validation and response rules
- Sign and verify using HS256 only and the configured `SECRET_KEY`.
- Require `sub`, `iat`, `exp`, `jti`, `iss`, and `aud` during decoding with zero leeway.
- Require `JWT_ISSUER` to match exactly and require at least one token audience in the configured `JWT_AUDIENCES` allowlist.
- Accept an audience string or string array only as untrusted input; after validation, project it to an immutable verified audience tuple.
- Reject malformed, expired, incorrectly signed, missing-claim, mismatched-trust-claim, and invalid-reference tokens. A legacy four-claim token without `iss` and `aud` is rejected.
- Return the same generic `401` response with `WWW-Authenticate: Bearer` for token failures.
- Do not preserve the raw bearer token, signing secret, or unrestricted decoded dictionary in trusted context.
- Authentication does not replace active-user, membership, RBAC, organization-scope, or tenant-binding checks.
- Token validation alone grants neither Runtime execution authority nor an external exactly-once guarantee.
- Keep the default access-token lifetime short; it is currently 30 minutes and configurable with `ACCESS_TOKEN_EXPIRE_MINUTES`.

## Secret requirements
Local development uses an explicit non-production default. Any environment other than development, local, or test rejects secrets shorter than 32 bytes and rejects known development or example placeholders. Generate a unique cryptographically random `SECRET_KEY` for each deployment as described in `.env.example`.

## Deferred lifecycle work
Refresh tokens and server-side revocation are not implemented because the MVP has no token persistence or revocation store. Clients discard access tokens locally, and tokens expire after their short lifetime. See `specs/decisions/ADR-003-jwt.md`.
