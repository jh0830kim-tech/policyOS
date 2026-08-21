# ADR-130: Runtime Connector Operation-Purpose Ownership

- Status: Accepted
- Date: 2026-08-21

## Context

ADR-125 requires a fresh observation-specific credential lease and prohibits reuse of the delivery
lease. ADR-129 simultaneously defined one immutable provisioning entry with one generic
`credential_purpose_reference`. The production acceptance candidate proved that this shape cannot
exact-match both delivery purpose `connector.invoke` and observation purpose `connector.observe`.
Sharing one purpose erases operation authority; duplicating the entry breaks the single destination
and provisioning identity.

## Decision

Sprint 16 retains exactly one immutable enabled provisioning entry. The generic
`credential_purpose_reference` is replaced by two required bounded fields:

- `delivery_credential_purpose_reference`, exactly `connector.invoke`; and
- `observation_credential_purpose_reference`, exactly `connector.observe`.

The values are non-empty, trimmed, distinct, immutable, and server-owned. Neither is inferred from
the endpoint, credential reference, request operation string, environment, recency, or the other
purpose.

Delivery selection receives a `RuntimeConnectorMaterializationRequest` and compares its exact
lease purpose only with `delivery_credential_purpose_reference`. Observation selection receives a
`RuntimeConnectorObservationMaterializationRequest` and compares its fresh lease purpose only with
`observation_credential_purpose_reference`. The concrete request type is the closed operation
discriminator; no caller-supplied union tag or generic operation selector is introduced.

Both paths continue to compare the same non-reusable provisioning reference, canonical HTTPS
endpoint, adapter identity and contract version, destination, credential reference, tenant,
organization, and classification ceiling. Missing, equal, swapped, stale, substituted,
cross-operation, cross-scope, cross-destination, cross-classification, or partial purpose binding
fails closed before secret materialization or transport construction.

The observation lease remains fresh and request-local. It cannot reuse the delivery lease request,
lease reference, capability, or secret buffer. Credential rotation behind the same explicitly
provisioned credential reference does not authorize purpose substitution.

The public production dependency bundle remains exactly nine fields. Facade signatures, Worker
handoff, CP8 evidence persistence, transaction ownership, and query non-mutation are unchanged.
Provisioning remains immutable process configuration; no table, backfill, normalization,
deduplication, schema change, or migration `20260808_0025` is required or approved.

## Required review sequence

1. Merge this governance correction independently.
2. Correct the provisioning public contract, selector, validators, production composition, and
   focused tests in a separately reviewed contract/production correction gate.
3. Resume provider-sandbox and PostgreSQL acceptance only after that correction is merged.
4. Require separate operator approval for any live endpoint, credential, deployment, tag, or
   release.

## Validation requirements

Architecture and later tests must prove single-entry cardinality, two exact distinct purpose
fields, operation-specific selection, rejection of shared, swapped, or substituted purposes,
fresh observation lease lifetime, unchanged destination and scope binding, unchanged nine-field
bundle, zero secret surfaces, and absence of migration `20260808_0025`.

## Alternatives considered

### Share one generic purpose

Rejected because it collapses delivery and observation authority and permits cross-operation
credential use.

### Create one catalog entry per operation

Rejected because Sprint 16 has one approved destination and one non-reusable provisioning identity;
duplicated entries introduce ambiguous or partial selection.

### Infer purpose from the request operation

Rejected because the provisioning catalog must carry authority explicitly and cannot manufacture a
credential purpose.

## Consequences

The follow-up correction changes a public immutable configuration shape but adds no new Runtime
authority. Production can exact-match delivery and observation without weakening purpose
separation, and the blocked acceptance candidate can resume without schema work.
