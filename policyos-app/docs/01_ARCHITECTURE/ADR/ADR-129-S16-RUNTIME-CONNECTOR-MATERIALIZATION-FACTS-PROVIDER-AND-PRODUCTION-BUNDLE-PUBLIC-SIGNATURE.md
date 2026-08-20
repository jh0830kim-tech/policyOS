# ADR-129: Sprint 16 Runtime Connector Materialization-Facts Provider and Production-Bundle Public Signature

- **Status:** Accepted for Sprint 16 governance preparation
- **Date:** 2026-08-21
- **Owners:** Runtime Architecture, Security, Operations
- **Related:** ADR-125, ADR-126, ADR-127, ADR-128

## Context

ADR-128 owns materialization identity and production composition but deliberately leaves exact
public model, method, managed-lifetime, leaf-factory and dependency-bundle signatures to a later
gate. Production code must not invent those signatures or expose private credential and transport
objects while implementing the connector.

## Decision

### Exact facts values

`RuntimeConnectorDeliveryMaterializationFacts` contains exactly
`runtime_connector_materialization_request_id`, `runtime_credential_lease_request_id`,
`connector_provisioning_reference`, `credential_reference`,
`credential_purpose_reference`, caller-supplied `requested_at`, and caller-supplied `expires_at`.

`RuntimeConnectorObservationMaterializationFacts` replaces only the first field with
`runtime_connector_observation_materialization_request_id`. Both values are strict, frozen and
extra-forbidden. Times are timezone-aware and `expires_at` is later than `requested_at`. Delivery
and observation identities, lease request IDs and lifetimes must be fresh and cannot be generated,
repaired, normalized or reused.

### Provider and managed lifetime

Covariant `MaterializationFactsT_co` is restricted to the two facts values. The runtime-checkable
`RuntimeConnectorMaterializationFactsProvider[MaterializationFactsT_co]` exposes exactly:

```python
def facts(self) -> MaterializationFactsT_co: ...
```

The provider performs no I/O and allows one successful call. Repeated or concurrent calls fail
closed. `RuntimeManagedConnectorMaterializationFactsProvider[MaterializationFactsT_co]` is an
async context manager. Its `__aenter__` returns the exact provider; `__aexit__` accepts the standard
exception triple and returns `Literal[False]`. Entry and exit occur exactly once and exit preserves
the primary exception.

The service layer defines two leaf factories:

```python
RuntimeConnectorDeliveryMaterializationFactsProviderFactory.__call__(
    prepared_delivery: RuntimeWorkerPreparedDelivery,
) -> RuntimeManagedConnectorMaterializationFactsProvider[
    RuntimeConnectorDeliveryMaterializationFacts
]

RuntimeConnectorObservationMaterializationFactsProviderFactory.__call__(
    invocation: RuntimeConnectorObservationInvocation,
) -> RuntimeManagedConnectorMaterializationFactsProvider[
    RuntimeConnectorObservationMaterializationFacts
]
```

Neither factory has a zero-argument, opaque-attempt or union-dispatch overload.

### Provisioning catalog

`RuntimeConnectorProvisioningEntry` contains exactly the provisioning reference, adapter
reference and contract version, destination reference, canonical `endpoint_uri`, tenant,
organization, classification ceiling, credential reference, credential-purpose reference and
`enabled: Literal[True]`.

`RuntimeConnectorProvisioningCatalog` contains exactly
`entries: tuple[RuntimeConnectorProvisioningEntry, ...]`; Sprint 16 permits exactly one entry.
The pure `select_runtime_connector_provisioning_entry` receives the catalog, exact prepared
connector facts and exact materialization facts. It rejects empty, duplicate, disabled, aliased,
redirecting, partial, cross-scope, cross-classification and credential-collision configurations.
It cannot select by URL, recency, partial scope or credential alone and performs no I/O.

### Observation preparation and outcome facts

`RuntimeConnectorObservationPreparationCapability.prepare` accepts exactly one
`RuntimeConnectorObservationInvocation` and returns one
`RuntimeConnectorObservationMaterializationRequest`. Its managed zero-argument factory owns the
observation facts-provider factory, exact catalog selection and one fresh broker call. Delivery
facts or leases cannot be accepted.

The existing `RuntimeConnectorOutcomeFactsProvider` methods remain unchanged. New
`RuntimeConnectorOutcomeFactsProviderFactory` accepts one closed delivery or observation
materialization request and returns a fresh request-scoped provider. It allows only the
operation-matched facts method once; wrong-operation, repeated and concurrent use fails closed.
It does not generate identities, times, references or digests.

### Public production bundle

Frozen, slotted, keyword-only `RuntimeConnectorProductionDependencyBundle` has exactly nine
fields: `provisioning_catalog`, `delivery_materialization_facts_provider_factory`,
`observation_materialization_facts_provider_factory`, `credential_broker_factory`,
`outcome_facts_provider_factory`, `pre_invocation_revalidation_factory`, `delivery_factory`,
`observation_preparation_factory`, and `observation_factory`. Every field is required and
structurally validated.

The broker field reuses the existing managed `RuntimeWorkerCredentialCapabilityFactory`.
Pre-invocation, delivery and observation factory signatures remain unchanged.

Private secret-materialization and HTTPS transport factories are deliberately not public bundle
fields. The process composition root supplies them only while constructing the concrete managed
delivery and observation factories. Runtime Ports, the Worker bundle and public exports cannot
name or retrieve them. This clarification supersedes any reading of ADR-128 that would expose
private factories as public fields.

### Security, sequencing and persistence

Missing, stale, substituted, cross-attempt, cross-destination, cross-scope,
cross-classification, changed-provisioning, changed-credential, changed-idempotency or expired
facts fail closed before secret materialization or network I/O. Delivery and observation retain
separate facts and leases. No database transaction spans provider access, broker acquisition,
secret materialization, transport, outcome facts or cleanup.

All new values are request-local and secret-free. Existing CP8 persistence remains authoritative.
No table, backfill, normalization, deduplication or migration `20260808_0025` is required or
approved. Facade five-parameter signatures and query non-mutation remain unchanged.

## Required review sequence

1. Merge this governance correction independently.
2. Implement the exact Port values, providers, catalog, service factories and nine-field bundle.
3. Implement private production composition in a separate gate.
4. Run provider-sandbox, PostgreSQL 16, cleanup and combined Worker acceptance separately.
5. Require separate operator approval for a real endpoint, credential, deployment, tag or release.

## Validation requirements

Architecture guards prove exact facts shapes, covariance, one `facts()` call, managed signatures,
two leaf factories, exact catalog selection, observation preparation, outcome provider factory,
exactly nine fields, broker reuse, private secret/transport exclusion, caller-owned identity/time,
and absence of migration `20260808_0025`.

Later tests cover strict parsing, time ordering, provider reuse, signatures, catalog collisions,
substitution, fresh observation lease, bundle construction, private-surface absence, immutable
exports and combined connector/Worker contract regression.

## Alternatives considered

### One union-dispatch facts factory

Rejected because it weakens operation-specific return typing.

### Put private secret and transport factories in the public bundle

Rejected because it exposes credential-material and provider-I/O capability.

### Let the catalog or provider construct missing values

Rejected because it creates hidden identity, time, destination and credential authority.

### Add migration `20260808_0025`

Rejected because the contracts add no durable fact.

## Consequences

The next contract gate can implement exact signatures without production-selected authority.
Private connector I/O remains hidden behind managed delivery and observation factories.
