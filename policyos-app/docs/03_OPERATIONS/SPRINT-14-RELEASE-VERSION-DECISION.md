# Sprint 14 Release Version Decision

## 1. Context

This governance checkpoint evaluates the project release version after Sprint 14. Sprint numbers,
domain contract versions, schema versions, migration revisions, protocol versions, and historical
tags are not project release versions. No Sprint 15 functionality, runtime behavior, tagging, or
publication is authorized here.

## 2. Preconditions

The checkpoint began on `feature/sprint-14-release-version-decision` at
`28f40f0fa96cb72ea197095281577403599a3a93`. After fetching `origin`, HEAD exactly matched
`origin/main`. The working tree contained no tracked or untracked changes visible to Git; status
reported only the accepted Windows ACL warnings below `tests/.knowledge_tmp/policyos-ingest-*`.
Merge commit `28f40f0` (Sprint 14 Final Release Checkpoint) is at HEAD. `pyproject.toml`,
`app/version.py`, the release policy, the final checkpoint, ADR-058 through ADR-064, and
`tests/test_sprint14_release.py` exist. The authoritative project version is `0.1.0`.

## 3. Authoritative version source

`[project].version` in `pyproject.toml` is the sole authoritative project release version.
`app.version.get_version` reads installed `policyos` package metadata and uses only
`0.0.0+unknown` for an unpackaged tree. FastAPI and OpenAPI use `get_version()`. The audit found
no duplicate production `__version__` constant, Git-derived runtime value, environment-selected
project version, Sprint-derived version, or automatic version-selection mechanism. Docker,
deployment, CI, and documentation references do not supersede package metadata. Caller-supplied
domain, contract, schema, migration, parser, model, and protocol versions remain independent.

## 4. Historical release audit

The tag inventory contains only `v0.9.0`. It is an annotated tag dated 2026-07-27 with the
message `Sprint 9 Intelligence Layer Complete`, targeting commit `26228a7`. At that target,
`pyproject.toml` reported `0.1.0` while FastAPI reported `0.2.0`. The repository also contains
free-form `v0.3` and `v0.4` release-candidate notes and a changelog mixing numbered versions,
Unreleased material, and Sprint headings. Repository evidence does not prove a corresponding
GitHub Release or external publication. This is inconsistent milestone metadata, not an
established project-release sequence. The historical tag remains untouched.

## 5. Sprint 14 change inventory

Relative to the merged version-policy checkpoint, Sprint 14 adds 46 files and 11,635 lines:
trusted source bindings; immutable metrics and aggregation contracts; Judge contracts and a
Judge decision bundle; decision packages; a decision pipeline and release-gate metadata; ADR-058
through ADR-064; and focused architecture, security, and release-marker tests. These are new
immutable packages with explicit public exports. They preserve tenant and organization identity,
classification, lineage, provenance, review boundaries, and deterministic validation.

## 6. Compatibility analysis

For known repository consumers, the additions are backward-compatible. Sprint 14 adds packages
rather than removing or renaming existing symbols, fields, enum values, routes, models, or
migrations. It changes no FastAPI route or OpenAPI surface, database model, Alembic revision,
deployment behavior, or existing serialized API contract. The stricter validation applies to the
new contracts themselves. Lifecycle states grant no permission; review, approval, authorization,
publication, deployment, transmission, and execution remain separate. External-consumer
compatibility cannot be proved because the repository does not identify external consumers or
their expectations.

## 7. Distribution-scope analysis

The repository does not prove whether the intended next artifact is an internal baseline, private
package, external package, GitHub source release, or prerelease candidate. Existing release notes
show preparation and operational checklists, but not publication. No evidence resolves current
publication intent or names the owner authorized to approve distribution. Therefore no
distribution scope is selected by this checkpoint.

## 8. Options evaluated

### Retain 0.1.0

Supporting evidence: it is the authoritative baseline and no distribution is approved.
Counterargument: Sprint 14 is substantial new capability, so retaining it as a released version
would hide meaningful change. Compatibility and migration impact are neutral; CI is unchanged.
It is appropriate only while the work remains unreleased. Rollback remains the current baseline.

### Advance to 0.1.1

Supporting evidence: known runtime, API, and database surfaces are unchanged. Counterargument:
11,635 lines of new contract capability are not primarily corrective. Calling this a patch would
misstate scope. Migration impact is none, but consumer expectations and release communication
risk would be poorly served. This option is rejected.

### Advance to 0.2.0

Supporting evidence: Sprint 14 adds substantial, additive capability while the project remains
pre-1.0; this is the best Semantic Versioning candidate for known consumers. There is no database
or deployment migration. Counterargument: external-consumer compatibility, distribution scope,
publication intent, and release ownership are unproved. Those unknowns block approval under the
release decision rules. If later approved, CI, changelog, release notes, package metadata, and
runtime/OpenAPI equality would need validation; rollback would redeploy the previous released
artifact without moving tags.

### Another pre-1.0 version

No policy or repository evidence supports another number, prerelease identifier, or Sprint-based
mapping. Such a choice would be arbitrary and would increase consumer and rollback ambiguity.

## 9. Selected version or explicit deferral

**VERSION DECISION DEFERRED**

No release version is approved. The authoritative project version remains `0.1.0` as an
unreleased baseline; this is not a claim that Sprint 14 has been released as `0.1.0`.

## 10. Rationale

Sprint 14 is substantial additive pre-1.0 capability, making `0.2.0` the semantic candidate.
Approval is nevertheless prohibited because distribution scope, external-consumer expectations,
publication intent, and release-approval ownership are unresolved. Explicit deferral avoids
turning a technically plausible number into an unsupported publication decision.

## 11. Changelog decision

`CHANGELOG.md` exists but mixes free-form Sprint entries, an Unreleased heading, and historical
numbered headings. Sprint 14 has no existing central changelog entry. Because no version is
approved and the release date and scope are unknown, this checkpoint does not change the
changelog or invent a date. Historical entries remain informational and unchanged.

## 12. Release-note decision

No Sprint 14 release-note file is created because no specific version is approved. A future
approved release should accurately cover the added contract layers; isolation, non-downgrade,
lineage, provenance, and separated authority controls; compatibility findings; metadata-only
limitations; lack of computation, aggregation, Judge runtime, deployment, publication,
transmission, or execution; and the documented Windows ACL test condition.

## 13. Tag policy

No tag is created. If a later checkpoint approves a version, its annotated `vX.Y.Z` tag may be
created only after the release PR is merged, metadata and notes agree, and CI is green. Tags are
immutable and must not be moved or repurposed. No exact tag command is recorded because a version
has not been approved.

## 14. GitHub Release policy

A GitHub Release is deferred. Policy recommends one for an externally distributed release and
makes it optional for an internal baseline, but the applicable scope is not established. This
checkpoint neither requires nor creates a GitHub Release.

## 15. Rollback and hotfix implications

There is no new release artifact to roll back and no new release line from which to hotfix.
Existing rollback guidance remains unchanged. After a future release, rollback must redeploy a
previously tagged artifact, and a hotfix must branch from the released commit and receive an
explicit patch-version decision; neither process may move or reuse a tag.

## 16. Known limitations

Sprint 14 provides metadata contracts and deterministic validation only. It performs no metric
computation, aggregation execution, runtime Judge operation, deployment, publication,
transmission, or decision execution. Distribution scope and external-consumer compatibility are
unknown. Historical version metadata remains inconsistent. Unfiltered tests may encounter the
accepted Windows ACL condition only under `tests/.knowledge_tmp/policyos-ingest-*`.

## 17. Sprint 15 relationship

Sprint 15 must not begin as part of this checkpoint. Governance permits Sprint 15 planning only
after this version-decision PR is reviewed and merged and CI confirms the recorded baseline.
Because no version is approved, Sprint 15 is not conditioned on tag creation or optional release
publication. Any broader organizational entry condition remains an owner decision.

## 18. Final governance decision

**VERSION DECISION DEFERRED**

Keep `pyproject.toml` at `0.1.0`. Do not modify `app/version.py`, the changelog, release notes,
domain contracts, or runtime behavior. Do not tag or publish. A future checkpoint may consider
`0.2.0` only after it identifies distribution scope, external consumers and compatibility
expectations, publication intent, and the authorized release owner, then reruns the complete
release validation.
