# ADR-128: Sprint 16 Runtime Connector Production Composition and Materialization Facts Ownership

- **Status:** Accepted for Sprint 16 governance preparation
- **Date:** 2026-08-21
- **Owners:** Runtime Architecture, Security, Operations
- **Related:** ADR-119, ADR-125, ADR-126, ADR-127

## Context

ADR-125 assigns final credential acquisition to pre-invocation revalidation and requires the
Worker to pass one closed connector materialization request to the delivery factory. ADR-126 and
ADR-127 define the private secret lifetime, exact wire protocol and caller-owned outcome facts.
The merged contracts expose those values but do not identify the trusted source of the UUIDs,
credential references and times needed to construct a delivery or observation materialization
request. They also do not close the process-lifetime factory graph that connects immutable
provisioning, the credential broker, private secret materialization, transport and outcome facts.

Production code must not generate those values, reconstruct them from an opaque attempt, select a
latest provisioning entry, read an environment credential or hide mutable request state in a
closure. The existing Worker still needs a composition-owned implementation that can satisfy the
request-accepting delivery factory without granting the Worker credential or transport authority.

## Decision

### Caller-supplied materialization facts

A later public-contract gate defines one request-scoped, server-owned, one-shot
`RuntimeConnectorMaterializationFactsProvider`. It supplies closed delivery and observation facts;
it does not acquire a credential lease, invoke a provider or create a result.

Delivery facts contain exactly:

- `runtime_connector_materialization_request_id`;
- `runtime_credential_lease_request_id`;
- `connector_provisioning_reference`;
- `credential_reference` and `credential_purpose_reference`;
- caller-supplied `requested_at`; and
- caller-supplied `expires_at`.

Observation facts contain the corresponding fresh
`runtime_connector_observation_materialization_request_id`, fresh
`runtime_credential_lease_request_id`, exact connector provisioning and credential references,
and caller-supplied `requested_at` and `expires_at`. Delivery and observation IDs and lease request
IDs must differ. Observation facts cannot predate the reconciliation request and cannot reuse a
delivery lease or request lifetime.

The provider is constructed for one exact prepared delivery or one exact observation invocation.
It permits one facts call and one exit. Missing, repeated, concurrent, stale, substituted,
cross-attempt, cross-destination, cross-scope, cross-classification or expired facts fail closed
before catalog lookup, broker acquisition, secret materialization or network I/O. No UUID, time,
reference, expiry or credential identity is generated or inferred by production composition.

### Immutable provisioning and exact lookup

The process composition root receives one immutable, already validated provisioning catalog. The
initial catalog contains exactly one enabled `POLICYOS_REFERENCE_NOTIFICATION_V1` entry and no
fallback. Exact lookup uses the provider-supplied non-reusable
`connector_provisioning_reference` together with the prepared connector, adapter contract,
destination, tenant, organization and classification ceiling. Lookup by endpoint, recency,
credential reference alone or a partial scope is prohibited.

The selected entry must exactly match the prepared envelope, facts-provider output and credential
lease request. Disabled, duplicate, replaced, partial, aliased, cross-scope or changed entries fail
closed. The catalog is process configuration, not authority, and cannot issue a permit, admission,
lease, result or observation.

### Pre-invocation preparation and broker ownership

The production `RuntimeWorkerPreInvocationRevalidationCapability` remains the sole delivery lease
owner. After the durable `DELIVERING` append it performs the exact current authority checks from
ADR-119, calls the delivery materialization-facts provider once, selects the exact provisioning
entry, constructs the strict credential lease request without altering any fact, and calls the
request-scoped credential broker once.

Only an exact `ISSUED` outcome whose request, lease, scope, provisioning, credential, permit,
attempt and lifetime facts match may be combined into the closed
`RuntimeConnectorMaterializationRequest`. Denied, missing, stale or mismatched outcomes return no
materialization request and perform no connector factory or network call. The Worker receives only
the validated secret-free request and calls
`delivery_factory(revalidation.materialization_request)` exactly once for `INVOKABLE`; every other
disposition calls it zero times.

### Production dependency graph

One immutable process-lifetime connector production bundle contains factories or immutable values
only. Its exact dependencies are:

1. the validated provisioning catalog;
2. a request-scoped delivery/observation materialization-facts provider factory;
3. a request-scoped credential-broker capability factory;
4. a request-scoped private secret-materialization source factory;
5. a request-scoped private HTTPS transport factory;
6. a request-scoped `RuntimeConnectorOutcomeFactsProvider` factory;
7. the exact pre-invocation revalidation factory;
8. the managed connector delivery factory; and
9. the observation preparation and managed observation factories.

The process bundle contains no bearer value, mutable secret buffer, HTTP client, session,
transaction, provider response, callback result or request-local capability. Partial bundle
construction fails application or Worker construction closed. Request capabilities are created
only after their exact request exists and are disposed exactly once in reverse construction order.

### Private secret and transport ownership

The secret-materialization source and HTTPS transport remain private production implementation
details. Their concrete interfaces are injected by the production connector factory and cannot be
imported by Runtime Ports, persisted, exposed through the Worker bundle or selected from mutable
global state. A real secret-manager vendor, endpoint and credential remain operator enablement
decisions.

The managed delivery or observation capability validates the request and provisioning before
materializing one secret into one private mutable request-local buffer. It builds the exact Bearer
header and canonical wire body privately, performs at most one transport call, validates the
closed response and uses the one-shot outcome-facts provider to construct the PolicyOS result or
observation. Cleanup overwrites and releases the secret buffer exactly once, closes transport
resources exactly once and preserves the primary validated outcome or exception.

No database transaction is open during broker acquisition, secret materialization, transport,
response parsing, outcome-facts production or cleanup. Pre-send rejection may be definitely not
delivered only when no request bytes crossed the governed call boundary. Every possible
transmission, timeout, disconnect, redirect, response or evidence uncertainty is ambiguous;
observation uncertainty is unavailable.

### Observation composition

Reconciliation has a separate request-scoped preparation capability. It receives the exact
ambiguous result and reconciliation request, calls the observation facts provider once, performs
the same exact provisioning lookup and acquires one fresh observation-specific lease. It returns
one closed `RuntimeConnectorObservationMaterializationRequest` to the managed observation factory.

The observation path cannot use the Worker delivery capability, delivery lease, delivery facts,
latest provider operation or a different destination. It performs at most one exact `observe`
call and preserves the four existing reconciliation outcomes without generating delivery
authority.

### Sequencing and failures

Delivery ordering is: durable `DELIVERING`, authoritative revalidation, facts once, exact catalog
lookup, broker once, closed request, managed factory once, private secret materialization, wire
encode, transport at most once, response validation, outcome facts once, result validation,
reverse cleanup, and later short-transaction lifecycle append.

Observation ordering is: exact reconciliation request, observation facts once, catalog lookup,
fresh broker lease, closed request, managed observation once, private transport, validated
observation facts, reverse cleanup, and later append through existing persistence.

Contract, authority, provisioning, credential, scope, classification, lineage, identity, digest,
time or result mismatches remain fail-closed programmer or security failures. Only the existing
bounded operational marker may represent backend unavailability. Cleanup failure cannot convert
ambiguous to delivered, delivered to failed, or any unavailable observation into certainty.

### Persistence and migration

All new facts are request-local and secret-free. Existing CP8 lifecycle and reconciliation
payloads remain authoritative for durable connector evidence. Provisioning remains immutable
process configuration, and secret material remains ephemeral. No table, column, provider-operation
aggregate, lease-use ledger, backfill, normalization, deduplication or migration
`20260808_0025` is needed or approved.

If operator requirements later demand mutable enablement, independently queried lease use,
durable provisioning replacement or provider-operation discovery outside the existing effect
identity, work stops for a separate schema-ownership governance gate.

## Required review sequence

1. Merge this governance gate independently.
2. Add the strict materialization-facts provider and immutable production-bundle public contracts.
3. Implement exact pre-invocation/observation preparation, private managed connector transport and
   Worker delivery-factory handoff in a separate production gate.
4. Run provider-sandbox, PostgreSQL 16, secret-cleanup, redirect, ambiguity, reconciliation and
   combined Worker acceptance.
5. Enable a real endpoint, secret, deployment, tag or release only by separate operator action.

## Validation requirements

Architecture guards must prove the exact delivery and observation facts, one-shot providers,
immutable bundle graph, exact provisioning lookup, one broker call, one managed factory call,
fresh observation lease, reverse exactly-once cleanup, no open transaction during I/O, bounded
failure meanings, caller-supplied identity/time, no public secret surface, Alembic single head
`20260808_0024`, and absence of migration `20260808_0025`.

Later focused tests must cover missing and repeated facts, cross-scope substitution, catalog
collision, credential denial, secret cleanup across success/failure/cancellation, zero calls for
blocked delivery, exact Worker handoff, valid and malformed acknowledgements, every transport
uncertainty and all observation outcomes. Provider-sandbox tests use only test credentials and a
local controlled receiver; governance performs no provider call.

## Alternatives considered

### Generate request IDs and times inside production composition

Rejected because hidden UUID and clock generation would become unreviewable authority.

### Let the Worker acquire the lease or reconstruct the request

Rejected because the Worker does not own credentials, provisioning lookup or materialization
facts and must treat the closed handoff as opaque.

### Store request-local preparation state globally

Rejected because mutable application state, service locators and cross-request reuse cannot prove
one-shot identity or cleanup.

### Reuse the delivery lease for observation

Rejected because reconciliation requires a fresh purpose-bound lease and later trusted time.

### Add migration `20260808_0025`

Rejected because all durable bounded evidence already has an authoritative existing owner.

## Consequences

Sprint 16 gains a complete construction and sequencing authority for the first production
connector without granting the Worker secret, network, clock or identity-generation powers. The
additional provider and factory layers are explicit, but they make cross-request reuse, hidden
generation, destination substitution and outcome rewriting independently testable.

ADR-129 fixes the exact public signatures deferred here. It uses separate delivery and observation
facts and leaf factories, one covariant managed provider, the exact provisioning catalog and a
nine-field secret-free public bundle. Private secret and HTTPS transport factories remain
composition inputs captured behind managed delivery and observation factories.

## ADR-130 operation-purpose clarification

Production catalog selection uses the concrete delivery or observation materialization request as
its closed discriminator. It compares the lease only with the corresponding explicit provisioning
purpose and never accepts a generic operation string, shared purpose, swapped purpose, endpoint
inference, or delivery lease for observation. This correction changes no factory graph, secret
lifetime, transaction boundary, public bundle field count, or persistence ownership.
