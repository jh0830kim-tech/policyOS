# Codex Prompt — Sprint 2 Step 1

Read `CODEX.md`, `POLICYOS_CONSTITUTION.md`, `specs/epics/EPIC-001-authentication.md`, `specs/features/FEATURE-001-password-security.md`, and `specs/features/FEATURE-002-jwt-access-token.md`.

Inspect the current project before editing. Existing identity models must not be recreated.

Implement only the authentication security foundation:

1. Add the minimum dependencies required for Argon2 password hashing and JWT.
2. Extend application settings with:
   - `jwt_algorithm`
   - `access_token_expire_minutes`
3. Create or update `app/core/security.py` with:
   - password hashing
   - password verification
   - signed access-token creation
   - safe access-token decoding
4. Add focused tests for correct and incorrect passwords, unique salted hashes, valid tokens, invalid signatures, and expiry.
5. Run:
   - `ruff check .`
   - `pytest`
6. Do not create the login endpoint yet.
7. Do not commit or push.

At completion, report:
- files changed
- dependency changes
- security design choices
- Ruff result
- Pytest result
- remaining work for the login API
