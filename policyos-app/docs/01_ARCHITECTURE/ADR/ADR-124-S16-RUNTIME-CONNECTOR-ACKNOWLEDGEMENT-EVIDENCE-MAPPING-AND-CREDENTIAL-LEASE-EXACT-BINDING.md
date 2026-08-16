# ADR-124: Sprint 16 Runtime Connector Acknowledgement Evidence Mapping and Credential Lease Exact Binding

- Status: Accepted
- Date: 2026-08-16
- Decision owners: Runtime Architecture, Security, Operations
- Related: ADR-085, ADR-086, ADR-123

## Context

ADR-123 selects the first production `CONNECTOR` boundary and requires a stable provider-issued
operation or resource identity plus canonical bounded acknowledgement evidence. The existing CP8
delivery result has separate result and acknowledgement reference/digest pairs, but their exact
mapping was not fixed. An ambiguous attempt may receive a stable provider identity before
acknowledgement validation fails. Losing that identity would prevent exact later observation,
while assigning it to an arbitrary field would create hidden meaning.

The existing credential lease binds scope, attempt, adapter, credential, classification, and
expiry, but does not carry every connector, destination, contract, envelope, idempotency, and
permit fact required by ADR-123. Production contracts cannot infer those facts from an opaque
reference or mutable configuration.

## Decision

### Closed delivery-evidence mapping

The existing `RuntimeEffectDeliveryResult` remains the authoritative local delivery-result fact.
For the initial connector:

- `acknowledgement_reference` is the stable provider-issued operation or resource identifier;
- `acknowledgement_digest_reference` is the digest of canonical, bounded acknowledgement
  evidence validated under the exact approved connector contract;
- `result_reference` is the caller-supplied bounded logical connector-result reference; and
- `result_digest_reference` is the caller-supplied digest of that logical result fact.

The acknowledgement pair is never synthesized from HTTP status, local invocation identity,
effect identity, idempotency key, response body, or a hash invented after the call. The logical
result pair does not replace or become provider acknowledgement authority.

`DELIVERED` requires both complete pairs and no failure pair. `DEFINITELY_NOT_DELIVERED` requires
bounded failure evidence proving that the send boundary was not crossed and contains neither a
logical result nor acknowledgement pair. `AMBIGUOUS` requires bounded failure evidence and may
retain the complete acknowledgement pair when a provider identity was observed but delivery
acknowledgement could not be validated. A partial pair is always invalid. Ambiguity never becomes
success merely because a provider identity exists.

### Reconciliation identity preservation

When an ambiguous result contains the acknowledgement pair, its exact
`acknowledgement_reference` is the only provider-operation identity eligible for later
provider-specific observation. The observation capability binds it to the same effect, connector,
destination, effect idempotency key, tenant, organization, classification, lineage, authority,
and permits. When the pair is absent, no provider identity may be inferred from a local record,
URL, timestamp, latest provider operation, or response fragment.

The existing ambiguous result identity and reconciliation request/observation records remain the
durable linkage. A provider operation is not an independently queryable PolicyOS aggregate in
this gate.

### Exact credential-lease binding

The later additive public-contract gate must carry and validate all of the following in the
credential lease request and issued opaque reference:

- tenant, organization, execution request, delivery attempt, actor, and optional agent instance;
- adapter family `CONNECTOR`, adapter reference, and adapter contract version;
- connector provisioning reference and exact destination reference;
- credential and credential-purpose references;
- classification and the exact canonical non-empty permit-reference tuple;
- delivery-envelope identity and envelope digest reference;
- stable effect identity and unchanged effect idempotency key; and
- caller-supplied requested, issued, and expiry times.

The broker and materialization factory validate request-to-reference equality. The managed
capability validates reference-to-envelope equality before entry and again immediately before
invocation. Missing, denied, expired, stale, substituted, cross-scope, cross-attempt,
cross-adapter, cross-connector, cross-destination, cross-envelope, changed-idempotency, permit, or
classification mismatch fails closed. No UUID, time, digest, revision, destination, or reference
is generated or inferred inside the broker, factory, capability, adapter, or Orchestration.

The opaque reference carries no credential material. Secret material remains confined to the
managed capability lifetime approved by ADR-123.

### Cleanup and delivery certainty ordering

Provider evidence validation establishes delivery certainty before managed-capability exit. If a
complete provider outcome has already been validated, a later cleanup failure cannot rewrite its
delivery certainty. Cleanup failure remains a bounded operational failure owned by future
production composition and must not disclose a secret or provider body.

If cancellation, process loss, or cleanup uncertainty prevents completion of provider-evidence
validation after transmission may have begun, the delivery outcome is `AMBIGUOUS`. A failure
before capability entry or before any request byte can be transmitted may be
`DEFINITELY_NOT_DELIVERED` only when the capability proves that the send boundary was not crossed.
This ordering does not authorize automatic retry.

### Persistence sufficiency

The existing CP8 lifecycle revision payload preserves the complete bounded delivery result,
including an acknowledgement pair on an ambiguous result. Existing reconciliation records
preserve the exact bounded observation and link to the ambiguous result through the approved
request identity. No new table, column, uniqueness constraint, backfill, normalization,
deduplication, or migration `20260808_0025` is required for this mapping.

If a later provider needs lookup by provider operation identity, durable connector provisioning,
lease-use uniqueness, or reconciliation discovery independent of the existing effect/result
identity, implementation stops for a separate schema-ownership and migration governance gate.

## Security and authority properties

- Every identity remains tenant-, organization-, classification-, lineage-, destination-, and
  attempt-bound.
- Provider bodies, secrets, tokens, authorization headers, clients, sessions, callbacks, and
  arbitrary metadata never enter Runtime contracts, persistence, audit, logs, or errors.
- Redirects, dynamic endpoints, fallback, latest-operation selection, and opaque-reference
  inference remain prohibited.
- Provider identity is evidence, not authority, permission, retry approval, or proof of delivery.
- Persistence stores caller-supplied bounded facts and never validates a provider response.

## Required review sequence

1. Merge this governance correction independently.
2. Add strict immutable credential-binding, managed connector, acknowledgement, and observation
   public contracts without production I/O.
3. Re-run persistence sufficiency review against the final provider contract.
4. Implement production broker and connector capabilities only after separate approval.
5. Complete PostgreSQL and provider-sandbox acceptance before enablement.

## Verification requirements

Architecture guards prove the closed four-field mapping, ambiguous provider-identity
preservation, exact lease fields, cleanup ordering, secret exclusion, and absence of migration
`20260808_0025`. Later contract tests cover strict/frozen/extra-forbidden behavior, complete pairs,
every mismatch dimension, one-shot lifetime, post-exit rejection, and all certainty outcomes.
Provider acceptance covers delivered acknowledgement, pre-send rejection, post-send timeout,
malformed acknowledgement, redirect refusal, cleanup failure before and after validated outcome,
and exact reconciliation identity.

## Alternatives considered

### Store the provider identity only for delivered outcomes

Rejected because an ambiguous attempt can receive a stable provider identity before validation
fails, and exact reconciliation must not search for a latest provider operation.

### Put the provider identity in `result_reference`

Rejected because ADR-123 makes it acknowledgement authority and the logical result pair has a
separate bounded meaning.

### Invent a local acknowledgement identity

Rejected because it cannot prove provider acceptance and would conceal missing external evidence.

### Add a provider-operation table now

Rejected because the existing append-only result payload preserves the required bounded evidence
and no independently approved lookup requires another schema owner.

## Consequences

The public-contract gate can extend opaque lease binding and define managed connector capabilities
without guessing evidence placement. Ambiguous outcomes retain exact provider identity when it
exists, while absence remains explicit and non-delivery is never inferred.

The mapping deliberately creates no provider-operation lookup, automatic retry, production
enablement, credentials, external calls, deployment, tag, or release.
