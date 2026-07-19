# Codex Prompt — Sprint 2 Step 7: Authentication Integration Tests


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

Create an end-to-end authentication and authorization regression suite.

## Required scenarios

1. Create or prepare a test user with a hashed password.
2. Login successfully.
3. Decode or use the returned access token.
4. Call `/api/v1/auth/me`.
5. Resolve an active organization membership.
6. Access a route with a granted permission.
7. Receive 403 for a missing permission.
8. Receive 401 for:
   - missing token
   - malformed token
   - expired token
   - invalid signature
9. Verify cross-organization membership and role isolation.
10. Verify no password hash appears in API responses.
11. Verify invalid user and wrong password have indistinguishable response status and public message.

## Quality rules

- Reuse current fixtures and async database patterns.
- Keep tests deterministic.
- Do not call external services.
- Do not create a parallel test application architecture.
- Fix implementation defects uncovered by tests, but do not expand unrelated scope.

## Validation

Run the complete test suite and provide the final pass count and warnings.
