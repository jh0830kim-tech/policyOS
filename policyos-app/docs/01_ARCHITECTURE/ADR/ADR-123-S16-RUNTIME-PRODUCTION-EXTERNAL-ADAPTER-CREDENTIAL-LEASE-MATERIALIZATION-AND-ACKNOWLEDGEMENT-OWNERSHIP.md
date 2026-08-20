# ADR-123: S16 Runtime Production External Adapter, Credential Lease Materialization, and Acknowledgement Ownership

- **Status:** Accepted for Sprint 16 governance preparation
- **Date:** 2026-08-16
- **Owners:** Runtime Architecture and Security
- **Related:** ADR-065, ADR-079, ADR-081, ADR-085, ADR-086, ADR-111 through ADR-122

## Context

Sprint 15 completed the governed Runtime API, PostgreSQL effect lifecycle, and delivery-only
Worker without enabling a real external adapter. `RuntimeAdapterPort` and
`RuntimeCredentialBrokerPort` are implementation-neutral boundaries, while the only concrete
Runtime adapters are deterministic fake and dry-run implementations.

The credential broker returns an opaque `RuntimeCredentialLeaseReference`; the governed envelope
carries only the lease identifier. No approved contract materializes secret content for a
concrete adapter. Selecting an environment variable inside an adapter, passing a secret through
an envelope, or resolving mutable global state would bypass lease, tenant, destination, and
request-lifetime boundaries.

ADR-085 requires destination-specific acknowledgement and reconciliation evidence before a
delivery can be called certain. A generic HTTP success code is transport evidence only and does
not prove that the intended external business effect occurred. Sprint 16 therefore requires this
governance decision before public contracts, persistence changes, or provider calls.

## Decision

### Initial production adapter boundary

The first production Runtime adapter family is exactly `CONNECTOR`. The first destination class
is one explicitly provisioned and approved HTTPS connector endpoint. The governed Registry and
prepared delivery facts name the exact connector, adapter contract, destination reference,
action, schema, effect identity, and idempotency identity before capability construction.

Dynamic URLs, caller-supplied endpoints, redirects, wildcard hosts, alternate destinations,
provider fallback, cross-tenant fallback, environment-selected destinations, and adapter-side
selection are prohibited. A redirect response is not followed and cannot amend the destination.
Another adapter family or destination class requires a separate governance gate and threat review.

### Enablement and redirect authority

Connector enablement is explicit server-owned provisioning bound to the approved Registry action
and destination reference. Possession of an endpoint, connector configuration, credential
reference, lease, Worker claim, or Adapter instance is not enablement or authority. Orchestration
revalidates current authority, permit, admission, Registry, destination, classification, lease,
deadline, cancellation, and effect bindings immediately before invocation.

The connector capability has no redirect authority. Only a separately approved provisioning
change may replace a destination and it cannot mutate an in-flight effect. Existing effects retain
their stable destination and fail closed when its provisioning is stale, disabled, substituted,
or missing.

### Credential ownership and materialization

The production credential broker owns credential-source access and lease issuance. It returns no
secret through public Runtime contracts. A separately reviewed factory materializes one
request-local managed invocation capability from the exact issued lease and approved connector
configuration.

The managed capability privately holds any materialized secret and binds it exactly to:

- tenant and organization;
- execution request, attempt, actor, and optional agent instance;
- adapter family, adapter reference, and adapter contract version;
- connector and destination references;
- credential and credential-purpose references;
- classification, permit references, issuance time, and expiry; and
- the immutable invocation envelope and stable effect idempotency key.

The capability is an asynchronous context manager with one invocation opportunity. It rejects
missing, denied, expired, stale, substituted, cross-scope, cross-attempt, cross-destination, and
post-exit use. Entry failure exposes no capability. Exit performs exactly-once cleanup after
success, failure, or cancellation. The secret exists only inside this request-local capability
for the minimum invocation lifetime and is never cached or reused across requests.

Secret material, tokens, passwords, private keys, authorization headers, clients, sessions, and
provider bodies never appear in the envelope, callback result, domain result, persistence,
audit, logs, metrics, exceptions, error responses, repr, serialization, or test snapshots.
Adapters may not read process environment, mutable application state, a service locator, or a
global credential provider.

### Invocation and cleanup ordering

Orchestration validates the exact prepared facts and durable `DELIVERING` boundary before the
managed connector capability is entered. It then revalidates cancellation, deadline, lease, and
credential validity, invokes the capability at most once, validates the bounded result, exits the
capability exactly once, and only then requests caller-supplied lifecycle persistence.

No database transaction remains open across credential acquisition, capability entry, network
I/O, acknowledgement validation, or cleanup. Cleanup failure cannot rewrite a validated provider
outcome or disclose a secret; any externally visible cleanup evidence requires a later explicit
public-contract decision.

### Acknowledgement authority

`DELIVERED` requires both:

1. a stable provider-issued operation or resource identifier bound to the exact connector,
   destination, effect idempotency identity, and request; and
2. canonical bounded acknowledgement evidence whose digest is validated by the connector
   capability.

The provider-issued identifier is the authoritative acknowledgement identity. PolicyOS does not
invent, hash into existence, parse from an unapproved free-form body, or substitute a local
request identifier for it. HTTP status alone, including any `2xx`, is not sufficient evidence of
delivery. Provider response bodies remain untrusted and are never persisted wholesale.

The bounded delivery mapping is closed:

- `DELIVERED`: the provider returned the stable identifier and exact validated acknowledgement
  evidence proving acceptance under the approved destination contract;
- `DEFINITELY_NOT_DELIVERED`: a validated rejection or failure occurred before any request bytes
  could be transmitted and the capability proves the send boundary was not crossed; and
- `AMBIGUOUS`: transmission may have begun, or timeout, disconnect, missing or malformed
  acknowledgement, redirect, process loss, cleanup uncertainty, or destination-state uncertainty
  prevents exact proof.

A provider rejection received after transmission is not automatically definite non-delivery. Its
provider-specific contract must prove that the rejection excludes the business effect; otherwise
the result remains `AMBIGUOUS`.

### Destination idempotency

The connector sends the existing stable effect idempotency key without normalization,
regeneration, attempt suffixes, or fallback keys. It validates an echoed idempotency identity when
the destination contract provides one. Destination idempotency can reduce duplicates but does not
produce a PolicyOS-wide exactly-once guarantee or remove crash and acknowledgement ambiguity.

Exact local replay performs no connector call. A new governed attempt uses the same stable effect
identity and idempotency key only after existing retry or reconciliation gates authorize it.

### Reconciliation observation

Only a provider-specific observation capability for the same provisioned connector and exact
destination may reconcile an ambiguous effect. It binds the same tenant, organization, effect,
destination, idempotency identity, authority, permits, classification, and lineage. It uses the
provider-issued operation or resource identifier when one exists and returns only the four
existing bounded outcomes.

Absence, lookup `404`, timeout, permission denial, expired credential, provider error, or missing
acknowledgement never implies confirmed delivery or confirmed non-delivery. A different endpoint,
connector, account, region, or credential scope cannot observe or reconcile the effect.

### Persistence and migration boundary

This governance gate adds no model, repository, schema, backfill, or migration
`20260808_0025`. Existing CP8 lifecycle revisions and reconciliation observations can store the
approved bounded result, acknowledgement, failure, and observation references and digests.

That sufficiency is conditional on the provider contract being representable by those existing
immutable references. If later investigation requires durable connector enablement,
credential-lease use evidence, an external-operation relational binding, reconciliation
discovery, or another independently queryable identity, implementation stops for a separate
persistence-governance gate. Existing rows may not be normalized, deduplicated, inferred, or
backfilled.

## Required review sequence

1. Merge this governance gate independently.
2. Define managed credential-materialization, connector invocation, acknowledgement, and
   observation public contracts without production I/O.
3. Perform a persistence sufficiency review and create a migration gate only if exact relational
   evidence cannot be represented by the existing CP8 schema.
4. Implement the production broker, connector capability, and observation capability.
5. Run focused, combined, PostgreSQL 16, and provider-sandbox acceptance before enablement.

Production enablement remains a separate operator decision. This ADR does not approve a real
credential, endpoint, provider account, deployment, tag, or release.

## Verification requirements

The governance gate proves:

- `CONNECTOR` and one explicitly provisioned HTTPS destination are the only initial boundary;
- dynamic destinations, redirects, environment selection, and fallback are prohibited;
- secret material exists only inside one managed request-local capability;
- exact lease, scope, attempt, adapter, connector, destination, permit, classification, and
  expiry binding is mandatory;
- cleanup is exactly once and cross-request or post-exit use fails closed;
- HTTP `2xx` alone never means delivered;
- the three delivery-certainty outcomes and four reconciliation outcomes remain closed;
- the stable effect idempotency key is preserved without an exactly-once claim;
- existing CP8 evidence remains the default persistence owner; and
- no production code, provider call, schema, or migration `20260808_0025` is introduced.

Later contract tests must cover strict and frozen models, one-shot lifetime, exact binding,
secret-surface exclusion, acknowledgement mapping, and reconciliation. PostgreSQL tests must
cover lifecycle atomicity, replay/conflict, rollback residue zero, ambiguity without blind retry,
and scope isolation. Provider-sandbox tests must cover verified acknowledgement, pre-send
rejection, timeout and disconnect ambiguity, redirect refusal, idempotent replay, credential
denial and expiry, and all four reconciliation outcomes.

## Alternatives considered

### Select any adapter family dynamically

Rejected because family selection becomes hidden authority and expands the initial threat surface.

### Let the adapter read environment credentials

Rejected because it bypasses the governed lease and cannot prove request-local lifetime, scope,
expiry, cleanup, or substitution resistance.

### Pass raw credentials through the envelope

Rejected because immutable contracts, persistence, logging, and error paths must remain
credential-free.

### Treat HTTP `2xx` as delivery

Rejected because transport acceptance does not prove the intended external business effect or a
stable provider acknowledgement.

### Follow redirects within the adapter

Rejected because a redirect changes the approved destination and can cross tenant, credential,
classification, and permit boundaries.

### Add migration `20260808_0025` now

Rejected because no provider-specific relational lookup has been approved. Schema follows a
proven durable evidence requirement and must not anticipate one by inference.

## Consequences

Sprint 16 has a narrow first real-adapter direction without weakening Sprint 15 local atomicity,
ambiguity, retry, or authority rules. The managed capability keeps secret material out of Runtime
facts while permitting a concrete connector to authenticate for one exact invocation.

The design deliberately treats many transport failures as ambiguous and may stop instead of
retrying. Provider enablement, contract implementation, persistence sufficiency, production I/O,
and deployment remain separate review units.

## ADR-124 evidence-mapping and lease-binding clarification

ADR-124 maps the stable provider-issued operation or resource identity to
`acknowledgement_reference` and the validated canonical bounded acknowledgement evidence digest
to `acknowledgement_digest_reference`. `result_reference` and `result_digest_reference` retain the
separate logical connector-result meaning. An ambiguous result may preserve a complete
acknowledgement pair for exact observation; the identity alone never proves delivery.

The additive credential contract must bind adapter contract version, connector provisioning,
destination, delivery envelope identity and digest, stable effect and idempotency identity,
canonical permits, scope, attempt, classification, credential purpose, and caller-supplied
lifetime. Provider validation precedes managed cleanup: cleanup after a validated outcome cannot
rewrite certainty, while uncertainty before validation after possible transmission remains
`AMBIGUOUS`. Existing CP8 payload persistence remains sufficient, so no migration
`20260808_0025` is introduced.

## ADR-125 provisioning and Worker handoff clarification

The initial destination is owned by one immutable process-lifetime provisioning entry whose
globally non-reusable provisioning reference is its version identity. Endpoint, credential,
scope, classification, connector, or adapter replacement requires a new reference. Production
composition injects the catalog, broker, and private secret materialization source; the Adapter
cannot read environment or mutable global state.

The pre-invocation owner returns one exact secret-free connector materialization request only for
an invokable result. The Worker passes it once to a request-accepting managed delivery factory.
Reconciliation uses a fresh observation-specific lease and materialization request and never
reuses the delivery capability.
