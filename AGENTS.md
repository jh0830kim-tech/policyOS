# PolicyOS AGENTS.md v3

These instructions apply to the Git repository rooted at:

`C:\Dev\policyOS`

The PolicyOS application is located at:

`C:\Dev\policyOS\policyos-app`

## 1. Operating model

PolicyOS is developed through a ChatGPT/Codex coding-agent workflow connected
to the local Windows workspace and GitHub.

The expected workflow is:

1. Prepare the required feature branch locally.
2. Confirm branch, HEAD, origin/main, and worktree state.
3. Ask Codex to inspect, edit, and validate only the current checkpoint.
4. Leave changes unstaged unless the user explicitly requests Git operations.
5. Review the final report.
6. Commit and push manually.
7. Open a pull request.
8. Require green CI before merge.

Do not assume that a local `codex` CLI command exists.

## 2. Windows editing limitation

The following error is a known environment limitation:

`windows unelevated restricted-token sandbox cannot enforce split writable root sets directly`

If this exact error occurs:

1. Do not retry the same or an equivalent `apply_patch`.
2. Do not claim that the edit succeeded.
3. Do not treat the failure as a PolicyOS source-code defect.
4. Continue read-only investigation when useful.
5. Report:
   - exact target file,
   - exact function or section,
   - minimal intended change,
   - smallest replacement block,
   - exact validation commands.
6. Do not use elevation, unsafe flags, unrestricted execution, or permission
   bypasses.
7. Do not silently switch to Python, PowerShell, shell, or filesystem-writing
   workarounds unless the user explicitly authorizes that editing method.

When the user applies the minimal change manually, resume from validation rather
than restarting the whole checkpoint.

## 3. Mandatory Git preconditions

Before implementation, run:

```text
git branch --show-current
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

When a checkpoint defines a required branch:

- Stop before editing if the branch does not match.
- Require a clean worktree unless expected existing changes are documented.
- Require `HEAD == origin/main` when starting from a fresh merged baseline.
- Do not create or switch branches unless the user explicitly requests it.

Known Windows ACL warnings are limited to:

`policyos-app/tests/.knowledge_tmp/policyos-ingest-*`

These warnings are environment conditions, not PolicyOS code failures.

## 4. Git safety

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

Never overwrite, discard, or reformat unrelated user changes.

Leave checkpoint changes unstaged unless commit or push is explicitly requested.

## 5. Checkpoint discipline

Implement only the active checkpoint.

Do not begin the next checkpoint automatically.

Every checkpoint must remain:

- deterministic,
- auditable,
- independently reviewable,
- independently testable,
- isolated from future layers.

When an approved checkpoint adds one runtime layer, update older architecture
guards only enough to allow that layer.

Approved sequence:

```text
CP0  architecture
CP1  authority
CP2  planning
CP3  state
CP4+ future layers only after explicit approval
```

Continue prohibiting future layers until their checkpoint begins.

## 6. Runtime dependency direction

Preserve this dependency direction:

```text
Sprint 14 immutable domains
    ↓
app.runtime.authority
    ↓
app.runtime.planning
    ↓
app.runtime.state
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

Rules:

- Sprint 14 packages MUST NOT import `app.runtime`.
- `app.runtime.authority` MUST NOT import planning or later runtime layers.
- `app.runtime.planning` MUST NOT import state or later runtime layers.
- `app.runtime.state` MUST NOT import orchestration or later runtime layers.
- Runtime domain packages MUST NOT import FastAPI, SQLAlchemy, Redis,
  workers, schedulers, provider SDKs, MCP clients, or connector clients.
- Reverse dependencies and dependency cycles are prohibited.

## 7. Authority and execution separation

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

Do not implicitly create approval, authorization, permit, admission, execution,
publication, transmission, deployment, retry, cancellation, compensation, or
state progression.

## 8. Immutable contract requirements

PolicyOS domain contracts should normally be:

- strict,
- frozen,
- extra-forbidden,
- deterministic,
- caller-supplied,
- timezone-aware,
- tenant-bound,
- organization-bound,
- classification-aware,
- revision-aware,
- free of mutable defaults,
- free of generated identifiers,
- free of hidden clocks,
- free of randomness,
- free of arbitrary metadata dictionaries,
- free of credentials, tokens, and secrets,
- free of filesystem, network, database, and subprocess I/O.

Do not silently:

- sort,
- deduplicate,
- normalize,
- infer,
- repair,
- broaden authority,
- lower classification,
- generate lineage,
- generate timestamps,
- load external resources.

Invalid values must fail closed with bounded typed errors.

## 9. Sensitive-data restrictions

Production contracts, errors, audit metadata, logs, and tests must not expose:

- raw prompts,
- chain-of-thought,
- raw model output,
- source-document content,
- passwords,
- access tokens,
- API keys,
- private keys,
- bearer credentials,
- unrestricted arbitrary payloads.

Use opaque references and bounded safe identifiers.

## 10. Minimal-change rule

Before editing:

1. Identify whether the problem is in production code, tests, documentation,
   CI, or the environment.
2. Reproduce the issue with the smallest focused command.
3. Change only the minimum required lines.
4. Prefer a test-only correction when production behavior is correct and an
   older checkpoint guard is obsolete.
5. Modify production code only when a focused test proves a real production
   defect.
6. Do not reformat unrelated files.
7. Do not modify upstream public contracts without an approved ADR.

## 11. Validation order

Use the smallest useful validation first:

1. Ruff on changed files.
2. The exact previously failing test.
3. Current checkpoint tests.
4. Direct upstream regression tests.
5. Combined relevant tests.
6. Import smoke.
7. `pip check` when required.
8. `git diff --check`.
9. `git status --short`.

Do not claim a suite passed unless it completed successfully.

Report:

- exact pass counts,
- warnings,
- timeouts,
- deselected tests,
- excluded modules,
- ACL conditions,
- commands not run.

## 12. Ruff and formatting

- Run `ruff check` on changed files.
- Use automatic fixes only when bounded and safe.
- Do not run repository-wide formatting for a checkpoint-local correction.
- Do not modify pre-existing formatting failures outside the task.
- Preserve configured line length and line endings.
- Treat LF/CRLF notices as warnings unless CI or `git diff --check` fails.

## 13. CI failure handling

When CI fails:

1. Inspect the exact failed job, test, and command.
2. Reproduce the exact command locally.
3. Determine whether the failure is:
   - introduced by the current checkpoint,
   - an obsolete earlier-checkpoint guard,
   - a pre-existing repository issue,
   - an ACL or environment issue.
4. Apply the smallest correction.
5. Re-run the exact failing test.
6. Do not weaken architecture boundaries beyond the current checkpoint.

## 14. Public API

- Use explicit immutable tuple exports.
- Do not use wildcard exports.
- Do not export private helpers, mutable registries, callbacks, SDK clients,
  persistence implementations, or runtime services.
- Preserve existing public contracts unless an approved ADR requires change.

## 15. ADR requirements

Every new architecture domain requires its approved ADR.

ADRs must document:

- context,
- package placement,
- dependency direction,
- authority boundaries,
- security and classification behavior,
- tenant and organization isolation,
- determinism,
- deferred scope,
- alternatives,
- consequences.

Documentation must not claim runtime capabilities that do not exist.

## 16. Final report integrity

Every final report must distinguish:

- files successfully modified,
- failed edits,
- files created,
- tests actually run,
- tests not run,
- warnings,
- environment failures,
- remaining blockers.

Always report:

```text
branch
HEAD
origin/main
files changed
focused test counts
Ruff result
import smoke result
pip check result when required
git diff --check result
git status --short
staged/commit/push/tag status
```

Never claim success based only on imports or a partial test run.

## 17. Stop conditions

Stop before implementation if:

- the required branch is wrong,
- the worktree is unexpectedly dirty,
- required merge ancestry is missing,
- an incompatible upstream contract change is required,
- a dependency cycle appears,
- classification cannot fail closed,
- immutable contracts would require raw secrets or credentials,
- metadata-only scope would require runtime execution,
- an unapproved project-version change becomes necessary.

When stopped, report the exact blocker and make no unrelated edits.
