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
