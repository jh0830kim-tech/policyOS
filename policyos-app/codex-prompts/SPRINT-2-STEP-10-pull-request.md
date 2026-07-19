# Codex Prompt — Sprint 2 Step 10: Pull Request Preparation

Read `CODEX.md`, `POLICYOS_CONSTITUTION.md`, and the Sprint 2 specifications.

## Preconditions

Proceed only when:

- the Sprint 2 branch is pushed
- CI-relevant local checks pass
- the user explicitly approves PR creation

## Required work

1. Compare `feature/sprint-2-auth-identity` with the repository's target branch.
2. Prepare a pull request title:

```text
Sprint 2: authentication, current user, and RBAC
```

3. Prepare a pull request description with:
   - purpose
   - implemented features
   - API changes
   - security decisions
   - tests and pass count
   - migrations
   - documentation updates
   - known warnings
   - deferred work
   - reviewer checklist
4. Create the PR only if the available GitHub tooling is connected and the user has explicitly requested creation.
5. Otherwise, provide the exact PR title and body for manual submission.
6. Do not merge the PR.

## Reviewer checklist

- [ ] Passwords use Argon2
- [ ] JWT validation is safe
- [ ] Login errors do not reveal account existence
- [ ] Current-user dependency rejects invalid tokens
- [ ] Organization isolation is enforced
- [ ] RBAC checks are server-side
- [ ] Security tests pass
- [ ] Ruff and Pytest pass
- [ ] Documentation is current
- [ ] No secrets are committed
