# ADR-058: Trusted Source Binding Layer

## Context and CP1 blocker

Sprint 14 CP1 found that several immutable Sprint 10-13 source records do not
carry every tenant, organization, classification, lineage, authorization, and
version field required by future Metrics consumers. Modifying those public
contracts would create an unrelated breaking change. Accepting incomplete or
inferred metadata would weaken tenant and classification boundaries.

## Decision and package placement

Introduce `app.source_bindings` downstream of all existing source domains and
upstream of future Metrics and Judge packages. Existing packages do not import
it. Upstream contracts are not modified. Trusted bindings supplement only
metadata absent from a source; existing source-native metadata cannot be
overridden.

## Source identity

`TrustedSourceIdentityReference` retains an exact closed source type, source
ID, optional version/revision, schema and contract versions, and owning package.
It performs no lookup, alias resolution, latest-version selection, or URI
resolution and embeds no source content.

## Governance and lineage context

`TrustedSourceGovernanceContext` retains exact tenant, organization,
classification, identity, policy, approval, decision, and permit references.
It creates no authorization. `TrustedSourceLineageContext` retains caller-
supplied lineage IDs and opaque digest references with source and binding
timestamps. It generates no digest, signature, graph, or attestation.

## Binding authority and authority matrix

`TrustedBindingAuthority` identifies the caller-declared authority. Authority
metadata is not cryptographic attestation.

- SOURCE_DOMAIN confirms source-native fields only.
- POLICY_ENGINE may supplement policy and authorization references.
- SECURITY_GOVERNANCE may supplement organization, classification, and lineage.
- EVALUATION_GOVERNANCE may supplement tenant, organization, classification,
  and lineage for governed evaluation consumers.
- ORGANIZATION_REGISTRY and TENANT_REGISTRY supply only their respective IDs.
- MIGRATION_AUTHORITY requires an explicit migration reference.
- MANUAL_REVIEW_AUTHORITY requires an explicit review reference.

No universal unrestricted authority exists. Supplemental categories are a
closed canonical tuple, not an arbitrary metadata dictionary.

## Complete and incomplete sources

Source-complete records require SOURCE_NATIVE origin, SOURCE_DOMAIN authority,
and exact equality for every native field. Source-incomplete records declare
each supplemental category and use an authority whose bounded matrix covers
those categories. Already-present tenant, organization, classification,
lineage, authorization, permit, version, revision, and timestamps remain exact.

## Classification and isolation

Missing classification never defaults to PUBLIC. A supplied classification
must equal or exceed each native and authority classification. Tenant and
organization are mandatory. Native values compare exactly; absent values must
be authority supplied. No global fallback, tenant-to-organization inference,
cross-tenant authority, or cross-organization authority is accepted.

## Authorization boundary

Bindings retain decision, approval, and permit identities without creating,
broadening, or executing authorization. Denied, revoked, superseded, or
invalidated sources cannot become usable merely through a binding. Possession
of a binding authorizes neither retrieval nor external transmission.

## Lifecycle, audit, and bundle semantics

Bindings are immutable revisions with ACTIVE, SUPERSEDED, REVOKED, or
INVALIDATED status. Only ACTIVE bindings may serve new consumers.
`TrustedSourceBindingAuditMetadata` is exact metadata and emits nothing.
`TrustedSourceBindingBundle` requires canonical caller ordering, unique source
identities, one tenant and organization, non-downgraded classification, related
lineage roots, ACTIVE status, and exact optional audit entries. It performs no
source loading or persistence.

## Determinism, security, compatibility, and consequences

All contracts are strict, frozen, extra-forbidden, caller supplied, timezone-
aware, and free of hidden clocks, generated IDs, hashing, I/O, registries, or
runtime enrichment. Raw prompts, outputs, evidence, credentials, secrets, and
authorization payloads are prohibited. Existing source schemas and release
versions remain unchanged.

Metrics must consume validated ACTIVE bindings whenever direct source metadata
is incomplete. Direct complete-source validation remains valid. This adds an
explicit governance step but prevents silent inference and upstream churn.

## Deferred scope

No source retrieval, persistence, API, worker, scheduler, provider/model/MCP/
connector call, cryptographic attestation, trust-store lookup, metric
computation, Judge, telemetry, dashboard, or authorization execution exists in
CP1-A. The Metrics Domain resumes under ADR-059.

## Alternatives considered

- Modify all upstream contracts: rejected as a coordinated breaking change.
- Accept incomplete metadata: rejected because validation could not fail closed.
- Infer organization from tenant or classification from source type: rejected
  because neither relationship is authoritative.
- Use observability events as authority: rejected because observation is not
  authorization or provenance proof.
- Arbitrary metadata dictionaries: rejected as unbounded and non-auditable.
- One unrestricted authority: rejected as authority escalation.
- Runtime enrichment or persistence-backed registry: rejected for hidden I/O,
  mutable state, and nondeterminism.
- Cryptographic attestation in CP1-A: rejected because opaque authority metadata
  does not establish a signing or trust-store architecture.
