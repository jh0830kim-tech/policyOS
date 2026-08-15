# ADR-110: CP9 Runtime Required-Audience Configuration Ownership

- **Status:** Proposed
- **Date:** 2026-08-15
- **Depends on:** ADR-087, ADR-091, ADR-100, ADR-106 through ADR-109, and migration
  `20260808_0024`

## Context

The verified access-token boundary accepts one or more configured JWT audiences. The trusted
Runtime application facade intentionally performs a stricter check: each Runtime operation must
be bound to one exact required audience. The merged production dependency bundle exposes only the
request-capability-scope factory, so it neither owns nor transports that configuration.

Production composition cannot safely choose the first configured audience, select one from token
claims, or infer one from prepared facts. Each approach creates hidden authorization policy and
makes configuration order, caller input, or request-local facts an authority source.

## Decision

### Authoritative setting

One required scalar setting named `runtime_api_required_audience` is the sole authoritative source
for the Runtime facade's exact `required_audience`. It is server-owned process configuration, not
an HTTP, token, preparation, dependency-bundle, persistence, or environment-selected object.

The resolved value must be a string that is non-empty, has no surrounding whitespace, and is no
longer than 200 characters. It must equal exactly one member of the configured immutable
`jwt_audiences` tuple. That tuple already rejects duplicates, so membership is unambiguous.

The setting is required and immutable after settings construction. Missing, non-string, empty,
whitespace-padded, oversized, or non-member values fail application construction. No default,
normalization, trimming, case conversion, fallback, or generated replacement is permitted.

### Prohibited selection and inference

Production must not select `jwt_audiences[0]`, sort the allowlist, use configuration-source
precedence as an audience-selection rule, choose an intersection from verified token claims, or
derive the value from claims, prepared facts, opaque references, request data, callback data,
dependency objects, or persisted records. Multiple verified token audiences do not weaken the
exact Runtime audience requirement.

The general JWT verifier continues to validate issuer, expiry, algorithm, and membership in the
configured audience allowlist. Runtime facade validation remains an additional exact check that
the authoritative required audience is present in `VerifiedAccessTokenClaims.verified_audiences`.

### Bundle and facade boundaries

`RuntimeApiProductionDependencyBundle` remains the frozen one-field public contract:

```text
request_capability_scope_factory: RuntimeApiRequestCapabilityScopeFactory
```

It gains no audience, settings, mapping, metadata, optional value, or selector. The production
application factory reads the already-validated scalar setting at construction and privately
captures it for facade construction. Request scopes and prepared packages cannot replace it.

The three facade operations retain their exact five-parameter public signatures. Existing
principal and command validation continues to receive one explicit `required_audience: str`; no
public Runtime contract or Protocol changes in this governance gate.

### Configuration correction gate

A separate config-contract correction gate may add the required frozen field to `Settings`, add
the example and test-process setting, and validate exact membership. It must prove field
immutability without freezing or otherwise changing the whole `Settings` model. It may not change
JWT issuance, the verifier's multi-audience allowlist, the production bundle, facade signatures,
or Runtime public contracts.

Only after that correction merges may the production composition gate construct the facade from
the exact validated setting. Existing unvalidated partial candidates must not be applied or reused.

### No persistence or migration

The required audience is process configuration and owns no durable Runtime fact. No table, model,
repository, backfill, normalization, deduplication, schema change, or migration
`20260808_0025` is required or permitted. Migration `20260808_0024` remains the single Alembic
head.

## Security and failure semantics

Configuration failure occurs before a Runtime request scope, preparation inspection, rate
admission, facade transaction, or HTTP operation begins. It cannot be converted to a caller-
selectable audience or repaired at request time. Error reporting remains bounded and must not
disclose bearer contents or cross-scope facts.

Tenant, organization, classification, lineage, permission, persisted binding, idempotency, and
transaction boundaries remain unchanged. Audience configuration grants no Runtime permission and
cannot replace facade-owned exact authorization.

## Validation matrix

- Governance: one authoritative scalar owner, exact membership, immutability, prohibited hidden
  selection, bundle one-field preservation, facade five-parameter preservation, and no migration.
- Config correction: required field; non-empty, trimmed, at most 200 characters; exact allowlist
  membership; immutable after construction; missing, malformed, and non-member rejection.
- Authentication regression: existing multi-audience token issuance and verification remain
  unchanged; Runtime requires the separately configured exact member.
- Production composition: the validated scalar is captured once at application construction and
  supplied to every facade without request-time selection or substitution.
- Architecture: no audience field in the production bundle, no public Runtime contract change,
  no production implementation in this gate, and Alembic head `20260808_0024`.

## Alternatives rejected

- Select the first allowlisted audience: tuple ordering is not authorization policy.
- Select an audience from token claims: caller-controlled evidence cannot choose server policy.
- Add the audience to prepared facts or request capabilities: request-local facts are not process
  configuration.
- Add the audience to the production dependency bundle: it violates ADR-107's exact one-field
  lifecycle entry point and duplicates configuration ownership.
- Accept any verified audience in the facade: it weakens the approved exact Runtime binding.
- Persist the setting: no durable Runtime authority or restart-recovery need exists.

## Consequences

Production composition has one explicit, deterministic audience source without broadening public
Runtime contracts. The additional required deployment setting is an operational cost and invalid
configuration now prevents application construction. This governance gate changes no production
Python, public contract, route, model, repository, schema, migration, data, tag, or release.

CP9 remains Planned / Blocked pending the config-contract correction, production composition and
routes, PostgreSQL/HTTP acceptance, regression, and closeout. CP10 remains Planned.
