# Codex Prompt — Sprint 2 Step 3: Current Authenticated User


Before editing, read:

- `CODEX.md`
- `POLICYOS_CONSTITUTION.md`
- `specs/epics/EPIC-001-authentication.md`
- `docs/03_API/API_GUIDE.md`
- `docs/03_API/ERROR_CODES.md`
- `docs/04_SECURITY/SECURITY.md`
- `docs/04_SECURITY/JWT.md`
- `docs/04_SECURITY/RBAC.md`

Inspect the existing implementation first. Do not recreate identity models. Preserve the current architecture and existing tests.

At completion:

- run `ruff check .`
- run `pytest`
- do not commit or push unless this prompt explicitly says so
- report files changed, design decisions, tests, warnings, and remaining work


## Goal

Implement bearer-token authentication and current-user resolution.

## Required behavior

1. Add an OAuth2 bearer-token dependency compatible with the existing login route.
2. Decode the access token using the Step 1 security utility.
3. Read the `sub` claim.
4. Resolve the user asynchronously from the database.
5. Reject:
   - missing token
   - malformed token
   - invalid signature
   - expired token
   - missing or invalid subject
   - nonexistent user
   - inactive user, when supported by the model
6. Return a generic HTTP 401 response with:
   - `WWW-Authenticate: Bearer`
7. Add `GET /api/v1/auth/me`.
8. Return a safe user response schema that excludes password hashes and internal security fields.

## Architecture

Prefer:

- `app/api/deps.py` for reusable authentication dependencies
- `app/schemas/auth.py` or an existing user schema module for the `/me` response
- existing async session dependency
- minimal router logic

Do not add organization membership or RBAC yet.

## Tests

Cover:

- valid token resolves current user
- `/auth/me` returns safe user data
- missing token returns 401
- malformed token returns 401
- expired token returns 401
- invalid signature returns 401
- nonexistent user subject returns 401
- inactive user returns 401 when supported
- response does not expose password hash
