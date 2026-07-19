# Codex Prompt — Sprint 2 Step 8: Documentation and Final Technical Review


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

Bring documentation and implementation into alignment before Git operations.

## Required work

1. Review all Sprint 2 code changes.
2. Update relevant documentation:
   - authentication behavior
   - login contract
   - current-user dependency
   - organization membership context
   - RBAC permission behavior
   - security limitations and deferred work
3. Update `CHANGELOG.md`.
4. Mark Sprint 2 status accurately in the roadmap.
5. Add or update `.env.example` when needed.
6. Check migration requirements.
7. Remove dead code, unused imports, duplicate helpers, and stale comments.
8. Confirm no secret or local credential is tracked.
9. Run:
   - `git diff --check`
   - `ruff check .`
   - `pytest`
10. Do not commit or push.

## Completion report

Provide:

- complete changed-file list
- API endpoints added
- permission architecture
- test count
- warnings
- deferred work
- recommended commit breakdown
