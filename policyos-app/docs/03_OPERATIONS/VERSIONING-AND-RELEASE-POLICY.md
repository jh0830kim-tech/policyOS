# Versioning and Release Policy

## Source of truth

PolicyOS uses Semantic Versioning. The authoritative release version is the
`[project].version` value in `pyproject.toml`. It is changed only by an
explicit release checkpoint and reviewed release PR. There is no second
manually maintained production version constant.

The application obtains its runtime version from installed `policyos` package
metadata through `app.version.get_version`. FastAPI and OpenAPI display that
same value. An unpackaged source tree returns the deterministic development
marker `0.0.0+unknown`; it performs no Git, network, or environment lookup.
Editable development installs expose the authoritative project version through
normal package metadata.

## Semantic Versioning

- Major: incompatible changes after a stable public contract is established.
- Minor: backward-compatible product or public-contract capability.
- Patch: backward-compatible corrections with no new public capability.
- Prerelease: `-alpha.N`, `-beta.N`, or `-rc.N` for explicitly approved
  non-final builds. Build metadata may identify artifacts but not precedence.

PolicyOS is currently pre-1.0. Breaking public contracts still require an
explicit release decision; they do not silently force a number from a Sprint.
Sprint numbers do not determine, calculate, or imply release versions.

## Tags and release process

Final and prerelease tags use `vX.Y.Z` plus an optional valid SemVer suffix.
Release tags are annotated, never lightweight. The release owner:

1. opens a release PR that intentionally updates `pyproject.toml` and the
   changelog;
2. runs version, release, application, and repository checks;
3. merges the approved PR;
4. creates the annotated tag on the merge commit;
5. optionally publishes a GitHub Release from that tag.

A GitHub Release is recommended for externally distributed releases but is not
required for an internal baseline. Automated checks may compare the proposed
tag with package metadata, but automation must not select, bump, or publish a
version without an explicit release checkpoint.

The changelog keeps upcoming work under Unreleased. A final release moves its
entries under the exact version and release date. Release notes and artifact
metadata use that same value.

## Alternatives considered

### A. pyproject.toml as source of truth — selected

Advantages: standard Python packaging, deterministic local/editable installs,
one reviewable value, direct CI and artifact integration. Disadvantages: source
trees without installed metadata need an explicit fallback. Tooling impact and
migration cost are small; reproducibility and release risk are favorable.

### B. dedicated version module

Advantages: trivial runtime import. Disadvantages: packaging metadata must be
synchronized or generated, creating duplication and extra build tooling.
Local use is simple, but CI, packaging, and migration risk are higher.

### C. Git tags as source of truth

Advantages: deployed provenance can match a release ref. Disadvantages: source
archives, shallow clones, editable installs, and untagged development become
ambiguous; builds need Git-aware dynamic-version tooling. It adds CI/build
complexity and makes reproducibility dependent on repository context.

### D. Sprint number maps to release version

Advantages: milestone labels are easy to communicate. Disadvantages: planning
cadence is not compatibility semantics, hotfixes and prereleases become awkward,
and existing Sprint/release history is inconsistent. It has high policy and
migration risk and was rejected.

## Current reconciliation and Sprint 13

Before this checkpoint, `pyproject.toml` declared `0.1.0`, FastAPI declared
`0.2.0`, release documents referenced `v0.3` and `v0.4`, and the annotated
`v0.9.0` tag pointed to Sprint 9 while metadata at that commit still reported
`0.1.0` and `0.2.0`. These facts show historical milestone labeling, not a
reliable version source. This checkpoint removes the runtime duplicate without
changing the authoritative `0.1.0` because repository evidence cannot prove
the correct next release number.

Sprint 13 receives no immediate tag. A later release checkpoint must identify
external consumers, compatibility expectations, distribution scope, changelog
contents, and the intended pre-1.0 release number. Only then may it choose and
apply a version bump before tagging.

## Hotfix, rollback, and automation

A hotfix branches from the released commit and proposes an explicit patch bump.
Rollback redeploys a previously tagged artifact; tags are immutable and never
moved or reused. Future CI should verify SemVer syntax, runtime/OpenAPI equality,
changelog presence, clean release state, annotated `vX.Y.Z` tag format, and
exact tag-to-project-version equality. It must consume package metadata rather
than Git at application runtime.

Sprint 14 may begin after this policy and its guards are reviewed and merged.
No Sprint 14 release may be tagged until a separate release checkpoint proves
and approves the intended version.
