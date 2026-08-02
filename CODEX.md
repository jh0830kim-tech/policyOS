# PolicyOS CODEX.md

This document defines the standard development workflow for ChatGPT/Codex
checkpoint work in PolicyOS.

`AGENTS.md` contains mandatory repository operating rules. This file explains
how to apply those rules during development.

## 1. Standard checkpoint workflow

### Phase A — Prepare

1. Merge the preceding checkpoint.
2. Switch to `main`.
3. Pull `origin/main`.
4. Confirm a clean worktree.
5. Create the required feature branch.
6. Confirm `HEAD == origin/main`.

Recommended commands:

```text
git switch main
git pull --ff-only origin main
git status --short
git switch -c <required-feature-branch>
git branch --show-current
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

### Phase B — Investigate

Before editing, Codex must inspect:

- applicable ADRs,
- current checkpoint prompt,
- upstream public contracts,
- existing tests,
- package dependency direction,
- similar prior contracts,
- CI workflow where relevant.

Codex must report package placement and compatibility findings before creating a
new architecture domain.

### Phase C — Implement

Implementation must be:

- checkpoint-local,
- contract-first,
- deterministic,
- immutable where required,
- free of future-layer implementation,
- free of unrelated refactoring.

### Phase D — Validate

Run focused validation first, then relevant regressions.

Never use a partial test run as evidence that the complete requested suite
passed.

### Phase E — Report

Return the exact requested final-report headings.

Leave changes unstaged unless Git operations were explicitly requested.

### Phase F — Review and merge

After user review:

1. Stage only intended files.
2. Inspect cached diff.
3. Commit with a checkpoint-specific message.
4. Push the feature branch.
5. Create a PR.
6. Require green CI.
7. Merge.
8. Delete the feature branch.
9. Synchronize local `main`.

## 2. Commit conventions

Preferred forms:

```text
feat(runtime): add immutable runtime authority domain
feat(runtime): add immutable execution planning domain
feat(runtime): add immutable execution state domain
test(runtime): allow CP3 state package
docs(runtime): define Sprint 15 runtime architecture
docs(codex): update repository operating rules
```

Use one logical purpose per commit.

Keep CI-only corrections separate from large feature commits when practical.

## 3. Pull-request conventions

Every PR should include:

- Summary
- Added or changed files
- Architecture boundaries
- Verification with exact counts
- Scope exclusions
- Known non-blocking warnings
- Confirmation of no version or tag change where applicable

Never claim repository-wide success if only a filtered or focused suite ran.

## 4. Architecture-guard evolution

Architecture guards are checkpoint-aware.

Examples:

- CP1 allows `authority`.
- CP2 allows `authority` and `planning`.
- CP3 allows `authority`, `planning`, and `state`.

When updating an older guard:

- remove only the newly approved layer from the forbidden list,
- keep every later layer prohibited,
- do not broaden the check,
- verify that the newly allowed directory actually exists,
- verify all deferred directories remain absent.

## 5. Windows apply_patch recovery

When the documented restricted-token error occurs:

1. Codex stops editing.
2. Codex provides the minimal replacement.
3. The user applies the change manually.
4. Codex resumes at focused validation.
5. The whole checkpoint is not restarted unless the worktree became ambiguous.

For large new-file checkpoints, repeated manual creation is inefficient.
The preferred long-term environment is a workspace in which the coding agent
has a supported writable sandbox. Native Windows restrictions may require WSL.

## 6. CP3 execution-state checklist

CP3 may create only the approved state-domain scope:

```text
policyos-app/app/runtime/state/
policyos-app/docs/01_ARCHITECTURE/ADR/ADR-075-...
policyos-app/tests/test_runtime_execution_state_domain.py
```

CP3 may narrowly update:

```text
policyos-app/app/runtime/__init__.py
policyos-app/tests/test_sprint15_runtime_architecture.py
policyos-app/tests/test_runtime_authority_domain.py
policyos-app/tests/test_execution_planning_domain.py
```

CP3 must continue prohibiting:

- orchestration,
- registry,
- ports,
- adapters,
- persistence,
- outbox,
- API,
- workers,
- schedulers,
- services,
- routes.

CP3 records state metadata only. It performs no live execution or operational
transition.

## 7. CI triage checklist

When a GitHub check fails:

1. Open the exact failing job.
2. Identify the first real assertion or command failure.
3. Ignore later cascading summaries.
4. Compare the failure against checkpoint architecture rules.
5. Reproduce the focused test locally.
6. Make one minimal correction.
7. Run:
   - changed-file Ruff,
   - exact failing test,
   - current checkpoint tests,
   - direct upstream tests,
   - architecture tests,
   - `git diff --check`.
8. Push only after local focused validation passes.

## 8. Version and release policy

Sprint numbers, checkpoint numbers, ADR numbers, and domain-contract versions
do not determine the project release version.

Do not modify:

- `pyproject.toml` project version,
- Git tags,
- changelog release entries,
- GitHub Releases,

without a separate approved release-governance decision.

## 9. Security baseline

Do not place the following in immutable contracts, error messages, audit
metadata, or logs:

- raw credentials,
- tokens,
- secrets,
- API keys,
- private keys,
- raw prompts,
- chain-of-thought,
- unrestricted model output,
- source-document contents.

Use bounded references.

## 10. Definition of checkpoint completion

A checkpoint is complete only when:

- implementation matches the approved architecture,
- focused tests pass,
- required regressions pass,
- Ruff passes,
- import smoke passes where required,
- `pip check` passes where required,
- `git diff --check` passes,
- CI passes,
- the PR is merged,
- local `main` is synchronized,
- no next-checkpoint work was mixed into the branch.
