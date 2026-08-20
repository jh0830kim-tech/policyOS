# ADR-125: Sprint 16 Runtime Connector Provisioning, Credential Materialization Handoff, and Worker Invocation Ownership

- **Status:** Accepted for Sprint 16 governance preparation
- **Date:** 2026-08-20
- **Owners:** Runtime Architecture, Security, Operations
- **Related:** ADR-114, ADR-119, ADR-123, ADR-124

## Context

ADR-123 and ADR-124 approve one managed HTTPS connector boundary and exact secret-free lease and
acknowledgement contracts. The persistence-sufficiency gate proves that existing CP8 payloads
preserve the resulting evidence. Production composition is still incomplete, however.

The Worker pre-invocation revalidation capability owns the final credential read, but its closed
invokable result exposes no exact connector materialization request. The Worker delivery factory
is zero-argument and returns a generic delivery Port, while the connector factory requires the
credential request, issued opaque lease reference, and exact invocation. Connecting these layers
through mutable state, a service locator, a repeated lease acquisition, or reconstruction from an
opaque reference would break ADR-114 and ADR-119.

The approved destination is also named only by bounded references. Existing connector settings
and legacy environment credential helpers do not constitute Runtime provisioning authority and
cannot select a production endpoint or secret for an invocation.

## Decision

### Immutable provisioning authority

Production composition receives one immutable, process-lifetime, server-owned connector
provisioning catalog. For the initial Sprint 16 boundary it contains exactly one enabled entry.
The entry binds:

- a globally non-reusable `connector_provisioning_reference`;
- connector ID, adapter reference, and adapter contract version;
- exact destination reference and one canonical HTTPS endpoint;
- credential and credential-purpose references;
- tenant and organization scope;
- classification ceiling; and
- an explicit enabled disposition.

The provisioning reference is the immutable version identity. An endpoint, credential,
classification, scope, connector, or adapter change requires a new reference; replacement under
an existing reference is prohibited. The application factory validates uniqueness, exact HTTPS
syntax, disabled alternatives, redirects, wildcard hosts, credentials, and cross-scope aliases
before serving or starting the Worker. Missing, duplicate, disabled, substituted, or ambiguous
provisioning fails application construction closed.

The catalog is configuration, not Runtime authority. It cannot grant a permit, admission,
Registry decision, credential lease, or delivery permission. Current authority and the exact
provisioning entry are both revalidated after durable `DELIVERING`.

### Credential broker and secret source

The process composition root injects the production credential broker and a private secret
materialization source. The broker alone issues an opaque lease reference from the exact
caller-supplied request. The private materialization source may resolve secret material only after
the request, issued reference, and provisioning entry compare exactly.

Secret bytes never enter a public Runtime model, Worker result, dependency bundle field,
persistence, audit, log, metric, exception, repr, or provider evidence. The connector adapter may
not read environment variables, a global credential provider, mutable application state, or a
service locator. Production startup fails closed when the injected broker, secret source, or
provisioning entry is absent. Choosing the concrete secret backend and provisioning a real secret
remain separate operator decisions.

### Closed pre-invocation handoff

For an `INVOKABLE` connector result, the pre-invocation revalidation capability returns exactly
one secret-free `RuntimeConnectorMaterializationRequest`. It contains the original exact
credential lease request, the newly issued opaque lease reference, the exact prepared invocation,
and caller-supplied request identity and time. The result is invalid when any duplicated fact
differs.

`DEFINITELY_NOT_INVOKED` and `SHUTDOWN_BLOCKED` results contain no materialization request. Replay,
conflict, shutdown, cancellation, deadline expiry, denied credentials, stale provisioning, or
binding failure therefore enters no connector capability and performs no external call.

The Worker treats the request as an opaque closed handoff. It does not create, alter, cache,
serialize, or infer any field and never receives secret material.

### Invocation factory and managed lifetime

The later public-contract correction changes the Worker delivery factory from a zero-argument
factory to one that accepts the exact `RuntimeConnectorMaterializationRequest`. It returns one
fresh managed `RuntimeEffectDeliveryPort` bound to that request. Its asynchronous context manager:

1. revalidates the request, lease, provisioning entry, scope, classification, permit, attempt,
   envelope, destination, idempotency identity, issuance, and expiry;
2. materializes the secret privately;
3. exposes one delivery call for the identical invocation;
4. validates the closed delivery result before exit; and
5. performs exactly-once cleanup in reverse construction order.

Concurrent entry, repeated delivery, substitution, use after exit, cross-request reuse, and a
different invocation fail before network I/O. Cleanup preserves the primary failure and cannot
rewrite validated delivery certainty. No database transaction is open during lease acquisition,
secret materialization, network I/O, acknowledgement validation, or cleanup.

### Reconciliation materialization

Reconciliation does not reuse the delivery lease or capability. A separate trusted preparation
capability obtains a fresh observation-specific credential lease and returns one closed
observation materialization request containing the exact observation invocation, lease request,
lease reference, provisioning reference, and caller-supplied requested time.

The managed observation factory accepts only that request and uses the same immutable
provisioning entry and exact destination. Missing provider identity, expired or denied credentials,
lookup absence, timeout, redirect, or provider error remains bounded observation-unavailable or
ambiguous evidence according to ADR-123 and ADR-124; it never infers delivery.

### Failure and sequencing

The exact Worker sequence is:

1. prepare, claim, and append `DELIVERING` through existing boundaries;
2. run one fresh pre-invocation revalidation;
3. stop without materialization for every non-invokable result;
4. pass the exact invokable materialization request once to the delivery factory;
5. enter, invoke, validate, and exit the managed connector once;
6. pass the exact result once to result completion; and
7. append caller-supplied lifecycle evidence through a fresh short transaction.

Operational unavailability may raise only the existing bounded Worker marker. Contract,
authority, scope, classification, provisioning, lease, or result mismatches remain programmer or
security failures and are not translated into a provider outcome or poll result.

### Persistence and migration

Provisioning remains immutable process configuration and secrets remain ephemeral. The
materialization requests and bounded results fit existing strict payload contracts and CP8
lifecycle/reconciliation persistence. This governance gate adds no durable provisioning table,
lease-use ledger, provider-operation aggregate, backfill, or migration `20260808_0025`.

If production operations later require mutable enablement, independently queryable lease use,
durable endpoint replacement, or provider-operation discovery, work stops before schema changes
for a separate persistence governance gate.

## Required review sequence

1. Merge this governance clarification independently.
2. Amend the Worker revalidation result, delivery factory, and observation materialization public
   contracts in a contract-only gate.
3. Implement immutable provisioning, broker/materializer, managed invocation and observation,
   and production composition in a separate gate.
4. Run PostgreSQL 16, HTTP/provider-sandbox, credential cleanup, redirect, ambiguity,
   reconciliation, and combined regression acceptance.
5. Enable a real endpoint or credential only through a separate operator decision.

## Validation requirements

Architecture and later tests must prove exact provisioning uniqueness, non-reusable references,
closed invokable handoff, no handoff on blocked results, one materialization and invocation,
exactly-once cleanup, secret-surface exclusion, fresh observation credentials, unchanged
idempotency, replay/conflict call count zero, cross-scope rejection, rollback residue zero, no
open transaction during I/O, and Alembic single head `20260808_0024`.

## Alternatives considered

### Let the delivery adapter reacquire a lease

Rejected because it duplicates the authoritative revalidation read and can select different
credential, time, scope, or provisioning facts.

### Store the handoff in mutable process state

Rejected because a map, service locator, context variable, or app state cannot prove one-shot
request identity and creates cross-request substitution risk.

### Let the adapter select endpoint or environment credential

Rejected because references are not endpoint or secret authority and adapter-side selection
bypasses provisioning and lease validation.

### Reuse the delivery lease for reconciliation

Rejected because reconciliation is a later independent operation with a fresh lifetime and may
require different current credential authorization while preserving the same destination.

### Add migration `20260808_0025`

Rejected because the approved initial provisioning is immutable process configuration and the
existing persistence gate already proves bounded evidence sufficiency.

## Consequences

The first production connector can be composed without hidden state, repeated credential reads,
or secret-bearing public facts. The Worker receives one exact secret-free handoff and remains
unable to select a provider, endpoint, credential, or result.

This governance requires a separately reviewed additive public-contract correction before
production implementation. It does not enable a connector, provision a credential, perform
external I/O, deploy, tag, or release.
## ADR-126 production seam clarification

The production Worker calls `delivery_factory(revalidation.materialization_request)` exactly once
only for an `INVOKABLE` result and never for replay, conflict, shutdown-blocked or definitely-not-
invoked outcomes. The resulting managed capability owns the private request-local secret buffer
and releases and overwrites it exactly once. No database transaction spans provider I/O.

The provisioned destination remains an exact pre-approved absolute HTTPS endpoint for
`POLICYOS_REFERENCE_NOTIFICATION_V1`; URL joining, redirects, query-selected destinations,
environment fallback and caller-supplied endpoints are prohibited. Provider response evidence
owns only the external operation identity and bounded acknowledgement. PolicyOS logical result
identity, trusted time and references remain owned by the one-shot
`RuntimeConnectorOutcomeFactsProvider`.

## ADR-128 materialization-facts and factory-graph clarification

The immutable catalog is selected only by the provider-supplied non-reusable provisioning
reference plus the exact prepared connector, adapter contract, destination, tenant, organization
and classification ceiling. Production code cannot select by endpoint, recency, credential alone
or partial scope.

A request-scoped one-shot materialization-facts provider supplies delivery and observation
materialization IDs, fresh credential lease request IDs, provisioning and credential references,
and caller-supplied requested/expiry times. Pre-invocation revalidation and observation
preparation each combine those facts with exactly one broker outcome. The process bundle contains
only immutable configuration and factories; request capabilities, private secret buffers,
transports and provider responses never become process-lifetime fields.
