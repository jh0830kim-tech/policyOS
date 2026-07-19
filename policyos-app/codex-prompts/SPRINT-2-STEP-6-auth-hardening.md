# Codex Prompt — Sprint 2 Step 6: Authentication Hardening


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

Harden Sprint 2 authentication without adding unnecessary product scope.

## Required work

1. Review the development JWT secret warning.
2. Ensure `.env.example` documents a strong secret requirement without containing a real secret.
3. Add configuration validation or a production-environment warning/error for weak secrets, consistent with the existing settings style.
4. Add authentication audit hooks or a minimal audit abstraction for:
   - login success
   - login failure
   - authorization denial
5. Do not store plain passwords, bearer tokens, or full sensitive request bodies in audit metadata.
6. Add a documented rate-limiting integration point for login.
7. Do not introduce Redis rate limiting unless the current project already has an established rate-limit subsystem.
8. Review all authentication error messages for credential or tenant leakage.
9. Review token payloads to ensure they contain no sensitive data.

## Optional refresh/logout decision

Do not implement refresh tokens or token revocation by default.

Instead, create an ADR or short design note explaining:
- why access-token-only is sufficient for the current MVP, or
- why refresh and revocation are now required.

Implement refresh/logout only when the existing architecture already supports token persistence or revocation and doing so is clearly justified.

## Tests

Add tests for any new validation, audit behavior, and safe error handling.
