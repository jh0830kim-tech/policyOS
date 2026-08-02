# PolicyOS Codex Operating Rules

These instructions apply to the Git repository rooted at `C:\Dev\policyOS`.

## 1. Windows editing reliability

If `apply_patch` fails with:

`windows unelevated restricted-token sandbox cannot enforce split writable root sets directly`

Codex MUST NOT retry the same or equivalent patch. Treat it as an environment
limitation, not a source-code defect. Check for another explicitly permitted
native editing mechanism. If none exists, stop only the edit and report the
exact target file, function or section, minimal intended replacement, and
validation commands. Never claim an unsuccessful edit was applied. Never use
elevation, unsafe flags, unrestricted execution, or permission bypasses.

## 2. Mandatory Git preconditions

Before implementation, run:

```text
git branch --show-current
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

When a task specifies a target branch, stop before editing if the branch does
not match. Require a clean worktree unless expected changes are documented.
Require `HEAD == origin/main` when starting a fresh checkpoint. Do not create or
switch branches unless the user explicitly requests it.

The known Windows ACL warnings are limited to:

`policyos-app/tests/.knowledge_tmp/policyos-ingest-*`

These warnings are environment conditions, not PolicyOS code failures.

## 3. Git safety

Unless the user explicitly asks, do not run:

```text
git add
git commit
git push
git tag
gh pr create
git reset --hard
git clean
git stash
git rebase
git branch -D
```

Never overwrite, discard, or reformat unrelated user changes. Leave
implementation changes unstaged unless commit or push is explicitly requested.

## 4. Small correction policy

For a one-line or small correction:

1. Identify the exact file, function, and failing invariant.
2. Reproduce the failure with the smallest focused test or Ruff command.
3. Modify only the minimum necessary lines.
4. Do not rewrite unrelated files.
5. Do not alter correct production code to satisfy an obsolete test.
6. Do not weaken architecture guards broadly.

When a checkpoint introduces one approved runtime layer, update older guards
only enough to permit that layer. CP2 may permit `planning` but must continue
prohibiting `state`, `orchestration`, `registry`, `adapters`, `persistence`,
`api`, `workers`, and later layers.

## 5. Dependency direction

Preserve:

```text
Sprint 14 immutable domains
    ↓
app.runtime.authority
    ↓
app.runtime.planning
    ↓
future app.runtime.state
    ↓
future app.runtime.orchestration
    ↓
future app.runtime.registry and ports
    ↓
future adapters
    ↓
future persistence and outbox
    ↓
future API and workers
```

Sprint 14 packages MUST NOT import `app.runtime`.
`app.runtime.authority` MUST NOT import planning or later runtime layers.
`app.runtime.planning` MUST NOT import state or later runtime layers.
Runtime domain packages MUST NOT import FastAPI, SQLAlchemy, Redis, workers,
schedulers, provider SDKs, MCP clients, or connector clients.
No reverse dependency or dependency cycle is permitted.

## 6. Authority and execution separation

Always preserve:

```text
DecisionPipeline is not an execution command.
ReleaseGate is not a permit.
Request is not authority.
Review is not approval.
Approval is not authorization.
Authorization is not a permit.
Permit is not admission.
Admission is not execution.
ExecutionPlan is not execution.
Plan validation is not authorization.
Execution state is not authority state.
Execution result is not a policy outcome.
```

Do not implicitly create approval, authorization, permit, admission,
execution, publication, transmission, deployment, retry, cancellation,
compensation, or state progression.

## 7. Immutable domain requirements

Domain contracts must normally be strict, frozen, extra-forbidden,
deterministic, caller-supplied, timezone-aware, tenant-bound,
organization-bound, classification-aware, revision-aware, and free of mutable
defaults, generated identifiers, hidden clocks, randomness, arbitrary metadata
dictionaries, secrets, credentials, and filesystem/network/database/subprocess
I/O.

Do not silently sort, deduplicate, normalize, infer, repair, broaden authority,
lower classification, generate lineage, or load external data. Invalid inputs
must fail closed with bounded typed errors.

## 8. Sensitive-data restrictions

Production contracts, errors, audit metadata, and logs must not contain raw
prompts, chain-of-thought, raw model output, source-document content,
passwords, tokens, API keys, private keys, bearer credentials, or unrestricted
arbitrary payloads. Use opaque references and bounded safe identifiers.

## 9. Editing scope

Determine whether the issue belongs to production code, tests, documentation,
CI, or the environment. Prefer a test-only correction when production behavior
is correct and an earlier checkpoint guard is obsolete. Change production code
only when a focused test proves a production defect. Do not modify protected
upstream contracts without an approved ADR. Do not reformat unrelated files.

## 10. Focused validation order

Run:

1. Ruff on the changed file.
2. The exact previously failing test.
3. Current checkpoint tests.
4. Direct upstream regression tests.
5. Combined relevant tests.
6. `git diff --check`.
7. `git status --short`.

For a CP2 planning correction, use:

```text
python -m ruff check tests/test_runtime_authority_domain.py
python -m pytest -q tests/test_runtime_authority_domain.py
python -m pytest -q tests/test_execution_planning_domain.py
python -m pytest -q tests/test_sprint15_runtime_architecture.py
python -m pytest -q tests/test_runtime_authority_domain.py tests/test_execution_planning_domain.py tests/test_sprint15_runtime_architecture.py
git diff --check
git status --short
```

Do not claim a suite passed unless it completed successfully. Report timeouts,
warnings, deselected tests, exclusions, and ACL conditions.

## 11. Ruff and formatting

Run `ruff check` on changed files. Apply automatic fixes only when bounded and
safe. Do not run repository-wide formatting for a checkpoint-local correction.
Do not modify pre-existing format failures outside the active task. Preserve
configured line length and line endings. Treat LF/CRLF notices as warnings
unless CI or `git diff --check` fails.

## 12. CI failure handling

Inspect the exact failed job, test, and command. Reproduce it locally.
Determine whether the failure is introduced by the current checkpoint, an
obsolete earlier-checkpoint guard, a pre-existing repository issue, or an
environment/ACL issue. Make the smallest correction. Re-run the exact failing
test. Do not weaken architecture boundaries beyond the current checkpoint.

## 13. Public API

Use explicit immutable tuple exports. Do not use wildcard exports. Do not
export private helpers, mutable registries, callbacks, SDK clients,
persistence implementations, or runtime services. Preserve existing public
contracts unless an approved ADR requires change.

## 14. ADR requirements

Every new architecture domain requires its approved ADR. ADRs must document
context, package placement, dependency direction, authority boundaries,
security and classification behavior, tenant and organization isolation,
determinism, deferred scope, alternatives, and consequences. Documentation
must not claim runtime capabilities that do not exist.

## 15. Final report integrity

Every report must distinguish files successfully modified, failed edits, files
created, tests actually run, tests not run, warnings, environment failures,
and remaining blockers.

Always report branch, HEAD, origin/main, files changed, focused test counts,
Ruff result, import smoke result, pip check result when required,
`git diff --check`, `git status --short`, and staged/commit/push/tag status.

Never claim success based only on imports or a partial test run.

## 16. Stop conditions

Stop before implementation if the required branch is wrong, the worktree is
unexpectedly dirty, required merge ancestry is missing, an incompatible
upstream contract change is required, a dependency cycle appears,
classification cannot fail closed, immutable contracts would require raw
secrets or credentials, metadata-only scope would require runtime execution,
or an unapproved project-version change becomes necessary.

When stopped, report the exact blocker and make no unrelated edits.
