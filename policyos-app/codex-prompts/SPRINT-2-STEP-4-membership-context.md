# Codex Prompt — Sprint 2 Step 4: Active Organization Membership


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

Resolve an authenticated user's active membership within an organization.

## Required behavior

1. Inspect existing Organization and Membership models and their fields.
2. Add a reusable dependency or service for organization-scoped membership resolution.
3. Use an organization identifier source consistent with the existing API architecture:
   - path parameter,
   - header, or
   - another already-established mechanism.
4. Do not invent a second competing organization-context mechanism.
5. Validate:
   - current user is authenticated
   - organization exists when disclosure is permitted
   - membership belongs to the user and organization
   - membership is active when the model supports status
6. Deny inaccessible organization context safely without leaking cross-tenant existence.
7. Return a typed membership/context object for later RBAC checks.

## Out of scope

- role and permission enforcement
- organization switching UI
- invitation workflow

## Tests

Cover:

- valid active membership resolves
- user without membership is denied
- membership in another organization is denied
- inactive membership is denied when supported
- organization isolation is preserved
