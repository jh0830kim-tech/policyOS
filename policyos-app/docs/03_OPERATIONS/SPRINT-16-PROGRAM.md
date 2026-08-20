# Sprint 16 Runtime Program

## 1. Purpose

Sprint 16 begins only with the explicitly approved production connector governance boundary. It
does not reopen or weaken the completed Sprint 15 CP0 through CP10 contracts. The first goal is
one reviewable path from a governed delivery attempt to one explicitly provisioned HTTPS
connector destination while preserving local-only atomicity and external uncertainty.

## 2. Baseline

- Git baseline: `7991e2aad69c8203bd18904dd963991b0591a969`.
- Alembic head: single `20260808_0024`.
- Sprint 15 CP9 Runtime API and CP10 delivery-only Worker are complete.
- Concrete Runtime adapters remain fake and dry-run only.
- Production credential materialization and real provider calls are absent.

## 3. First governed capability

ADR-123 limits the initial production family to `CONNECTOR` and one explicitly provisioned HTTPS
destination class. Dynamic URL input, redirects, destination fallback, wildcard routing, caller
selection, and implicit environment selection are prohibited.

One request-local managed capability owns secret materialization and one invocation opportunity.
It binds the exact issued credential lease to tenant, organization, attempt, adapter, connector,
destination, classification, permits, expiry, envelope, and stable effect idempotency key. Secret
material is never a Runtime contract or persistent fact and is cleaned up exactly once.

## 4. Delivery and acknowledgement

- `DELIVERED` requires a stable provider-issued operation or resource identity plus validated
  bounded acknowledgement evidence.
- HTTP `2xx` alone is not delivery evidence.
- `DEFINITELY_NOT_DELIVERED` requires proof that no request bytes crossed the send boundary.
- Any possible transmission, redirect, timeout, disconnect, missing acknowledgement, malformed
  acknowledgement, process loss, or unknown destination state is `AMBIGUOUS`.
- The existing effect idempotency key is passed unchanged; no external exactly-once guarantee is
  claimed.
- Reconciliation uses only a provider-specific observation capability for the same connector and
  exact destination and retains the four existing bounded outcomes.

## 5. Review sequence

| Gate | Purpose | Excluded |
| --- | --- | --- |
| S16 ADR-123 Governance | Fix connector, credential, acknowledgement, and persistence boundaries | Production/public Python, provider calls, schema |
| S16 Connector Contracts | Define managed materialization, invocation, acknowledgement, and observation contracts | Production I/O and credentials |
| S16 Persistence Sufficiency | Prove existing CP8 references are sufficient or stop for a schema ADR | Inferred schema and backfill |
| S16 Production Connector | Implement broker, managed connector, and observation capabilities | Dynamic providers and fallback |
| S16 Provider Acceptance | Exercise sandbox acknowledgement, ambiguity, credential, idempotency, and reconciliation paths | Production credentials and deployment |

Each gate requires an exact file scope and independently green CI. Ready and merge remain explicit
review operations. Production enablement, tag, release, and credential provisioning are separate
operator decisions.

## 6. Persistence boundary

ADR-123 creates no schema or migration `20260808_0025`. Existing CP8 lifecycle and reconciliation
records remain the default bounded evidence owner. If a provider-specific contract needs durable
connector enablement, lease-use evidence, external-operation relational identity, or
reconciliation discovery, work stops before implementation for a separate migration decision.
Backfill, normalization, deduplication, and inferred provider identity are prohibited.

## 7. Validation matrix

Governance and contracts must prove strict immutable facts, exact scope and lease binding,
one-shot managed lifetime, exactly-once cleanup, secret-surface exclusion, closed acknowledgement
mapping, unchanged idempotency identity, and bounded reconciliation.

PostgreSQL 16 acceptance must preserve lifecycle append atomicity, exact replay, conflict,
rollback residue zero, tenant and organization isolation, exact classification, and zero blind
retry after ambiguity. Provider-sandbox acceptance must cover verified acknowledgement,
pre-send rejection, timeout, disconnect, redirect refusal, idempotent replay, denied or expired
credentials, and every reconciliation outcome.

## 8. Security and exclusions

No raw prompt, source content, model output, provider body, credential, token, private key,
authorization header, client, session, callback, arbitrary metadata, SQL detail, traceback, or
cross-tenant existence may enter Runtime facts, persistence, audit, logs, metrics, or errors.

Sprint 16 does not authorize another adapter family, queue, autonomous scheduler, generalized
retry, automatic redrive, cross-tenant execution, external business-effect exactly-once,
production deployment, tag, or release.

## 9. ADR-124 contract correction

Before managed connector contracts, ADR-124 fixes the evidence mapping. The provider-issued
operation or resource identity is the acknowledgement reference and the canonical validated
evidence digest is its acknowledgement digest. Logical result references remain separate.
Ambiguous results retain a complete acknowledgement pair when available so reconciliation never
selects a latest provider operation or invents an identity.

Credential lease requests and references must bind the exact connector, destination, adapter
contract, envelope and digest, stable effect idempotency key, permits, tenant, organization,
attempt, classification, credential purpose, and lifetime. Validation precedes cleanup; cleanup
after a validated provider outcome cannot rewrite certainty. The correction adds no production
I/O, provider-operation table, backfill, or migration `20260808_0025`.

## 10. Managed connector contract gate

Public Ports now define an exact credential materialization request, a one-shot managed connector
invocation capability, a provider-specific managed observation capability, and pure binding
validators. Lease request/reference equality covers every ADR-124 identity and rejects stale,
substituted, cross-scope, cross-attempt, cross-destination, changed-idempotency, permit, and
classification mismatches before capability use.

The gate validates the three closed delivery certainties and exact reconciliation binding without
networking or secret material. PostgreSQL and provider-sandbox execution remain later gates;
existing payload persistence remains unchanged and Alembic stays at `20260808_0024`.

## 11. Connector persistence sufficiency gate

The existing CP8 revision graph is the authoritative connector evidence owner. Delivery outcome
facts round-trip through lifecycle revision `result_payload`; provider-specific observations
round-trip through reconciliation `observation_payload`; and the exact closed reconciliation
request round-trips through registry `request_payload`. Strict allowlisted serialization rejects
extra, unknown, and substituted facts, and exact relational scope continues to bind tenant,
organization, classification, lineage, effect, attempt, revision, request, and digest identity.

PostgreSQL 16 acceptance must prove append-only storage, exact replay, conflict rejection,
rollback residue zero, and cross-scope substitution rejection. No provider-operation table,
credential-secret storage, connector evidence backfill, normalization, deduplication, or migration
`20260808_0025` is authorized. Production connector behavior remains the next independent gate.

## 12. Connector provisioning and Worker handoff governance

ADR-125 fixes the production composition seam before connector implementation. One immutable
server-owned provisioning entry binds the non-reusable provisioning version reference to the
exact HTTPS endpoint, connector, adapter contract, destination, credential references, scope, and
classification ceiling. Partial, duplicate, disabled, substituted, redirecting, or ambiguous
configuration fails application construction closed.

Pre-invocation revalidation is the sole delivery lease owner and returns a closed secret-free
materialization request only when invocation remains authorized. The Worker passes it once to the
managed delivery factory. Observation preparation obtains a fresh lease for the same immutable
destination. The next contract gate amends these signatures; production I/O and provider
acceptance remain later gates, with no schema or migration `20260808_0025`.

## 13. Connector Worker materialization handoff contracts

The pre-invocation result has a closed disposition-dependent shape: `INVOKABLE` contains exactly
one validated connector materialization request, while `DEFINITELY_NOT_INVOKED` and
`SHUTDOWN_BLOCKED` contain none. The Worker delivery factory accepts only that request and cannot
reacquire a lease or infer connector facts.

Observation preparation produces a separate materialization request and fresh
observation-specific lease. Its caller-supplied request time is exact and cannot predate the
reconciliation request, preventing reuse of the earlier delivery lease request. Production
broker, secret materialization, provider I/O, PostgreSQL acceptance, and provider-sandbox
acceptance remain later gates. This gate adds no schema or migration `20260808_0025`.
