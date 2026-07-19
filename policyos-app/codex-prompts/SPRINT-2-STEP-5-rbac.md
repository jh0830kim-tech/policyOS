# Codex Prompt — Sprint 2 Step 5: RBAC Authorization


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

Implement organization-scoped role and permission checks using the existing:

- Role
- Permission
- RolePermission
- MembershipRole

models.

## Required behavior

1. Inspect actual relationship fields before implementing.
2. Add a reusable authorization dependency or service.
3. Support atomic permission names such as:
   - `policy.read`
   - `policy.create`
   - `policy.review`
   - `policy.approve`
   - `member.manage`
   - `role.manage`
   - `agent.execute`
   - `audit.read`
4. Resolve effective permissions through the active membership.
5. Return HTTP 403 for authenticated users lacking permission.
6. Keep HTTP 401 for authentication failures.
7. Do not use UI visibility as authorization.
8. Avoid loading or exposing unrelated organization data.
9. Add one minimally invasive protected test route only if no suitable route exists.

## Suggested API

A pattern such as:

```python
Depends(require_permission("policy.read"))
```

is preferred when it fits the project.

## Tests

Cover:

- authorized membership succeeds
- membership without required permission gets 403
- role in another organization does not grant access
- multiple roles combine permissions correctly
- missing authentication remains 401
- permission names are evaluated exactly
