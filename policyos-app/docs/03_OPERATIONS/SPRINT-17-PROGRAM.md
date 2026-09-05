# Sprint 17 Program: Runtime Connector Operator Enablement

## Status

`COMPLETED WITH DEPLOYMENT DEFERRED`

Sprint 17 starts from Sprint 16 closeout at merge baseline
`12dade7aeadcd5e76763c685a11c46266045bb39` and Alembic single head
`20260808_0024`.

## Goal

Prepare the merged single-destination HTTPS Runtime connector for controlled operator enablement
without activating a live provider, exposing a credential, or creating hidden mutable provisioning
authority.

The initial operating model is one deployment-owned immutable, secret-free manifest. PolicyOS
does not own a provisioning mutation API or database registry, and migration `20260808_0025` is
not approved.

## Checkpoints

1. **ADR-131 governance:** manifest, operator, secret backend, deployment, kill-switch, telemetry,
   and persistence ownership.
2. **Operator configuration contracts:** strict immutable manifest and construction-time validation.
3. **Private backend composition:** deployment-selected secret manager and HTTPS transport behind
   the existing private request-scoped interfaces.
4. **Process entrypoint and runbook:** explicit dependency wiring, startup failure, controlled
   replacement, rotation, revocation, rollback, and incident procedures.
5. **Pre-production acceptance:** provider sandbox, PostgreSQL lifecycle/reconciliation evidence,
   egress/TLS/redirect controls, ambiguity, cleanup, and process-lifetime tests.
6. **Controlled enablement:** separate operator approval for endpoint, credential, deployment, and
   any external provider traffic.
7. **Observation and rollback drill:** exact provider observation, revocation, replacement, and
   rollback evidence.
8. **Sprint 17 closeout:** merged evidence, single Alembic head, clean worktrees, and consistent
   roadmap/program/security status.

## Mandatory boundaries

- one pre-approved provider, destination class, HTTPS endpoint, and provisioning revision;
- no dynamic URL, redirect, caller endpoint, environment-selected object, or global fallback;
- no secret in contracts, manifest, persistence, audit, logs, errors, or provider evidence;
- exact tenant, organization, classification, lineage, attempt, destination, credential,
  provisioning, idempotency, and time bindings;
- no automatic activation, retry, redrive, provider discovery, or external exactly-once claim;
- no PolicyOS provisioning registry or migration `20260808_0025`;
- Ready, merge, deployment, tag, release, credential provisioning, and live provider traffic remain
  separately authorized actions.

## Stop conditions

Stop before implementation when a checkpoint requires mutable PolicyOS-owned enablement, a durable
provisioning or lease-use identity, provider-operation discovery outside existing effect identity,
schema ownership, inferred backfill, another adapter family, another destination, or a new public
authority. Resolve those requirements in a separate governance gate.

## Validation matrix

- focused ADR-131 architecture guard;
- combined Sprint 16 and Sprint 17 governance regression;
- strict UTF-8/LF, Ruff, AST, import, `pip check`, and diff validation;
- exact construction-time manifest rejection matrix;
- secret-surface, endpoint-substitution, redirect, TLS, egress, rotation, revocation, cleanup,
  ambiguity, observation, replay, and rollback tests at their implementation checkpoints;
- PostgreSQL 16 only when persistence/transaction evidence is exercised;
- provider sandbox before any separately approved live-provider action;
- Alembic single head `20260808_0024` and migration `20260808_0025` absence.

The operator configuration contract reuses the exact one-entry provisioning catalog as the
runtime manifest representation. Construction accepts only the canonical path
`/v1/runtime/connector`; alternate paths, a trailing slash, query, fragment, userinfo, or non-HTTPS
endpoint fail closed. The provisioning reference remains the immutable version identity, with no
second manifest wrapper or runtime digest/signature authority.

## Deferred

Another adapter family or destination, content-bearing payload materialization, autonomous redrive,
external business-effect exactly-once, PolicyOS-managed provisioning, production credentials,
provider deployment, tag, and release are outside this governance checkpoint.

## ADR-132 deployment-neutral backend gate

The private backend checkpoint uses one deployment-injected, version-pinned secret accessor and a
hardened request-local `httpx` transport. The deployment operator, not PolicyOS configuration,
selects the concrete secret-manager vendor, workload authentication, credential version, rotation,
revocation and access-audit policy.

The later implementation must reject missing, unversioned, stale, substituted, revoked,
cross-purpose and cross-scope accessor results before I/O; use one mutable request-local secret
buffer; overwrite and release it exactly once; disable environment proxy/trust selection,
redirects, retries and fallback; and preserve ambiguity for every post-call failure. It adds no
schema or migration `20260808_0025`. Process entrypoint/runbook and pre-production acceptance
remain separate checkpoints, and live provider enablement still requires operator approval.

## ADR-133 trusted deadline-clock gate

Production transport receives no ambient time authority or default timeout. A request-scoped
managed trusted UTC clock validates one expected reference and is read exactly once immediately
before the network-call boundary. The exact caller deadline minus that reading must be positive and
is passed unchanged to connection, pool, write, and read bounds. There is no rounding, clamp,
refresh, fallback, or second clock read.

Deadline exhaustion, missing clock configuration, stale or substituted readings, and non-UTC time
fail before transport invocation. Timeout or cancellation after invocation preserves ambiguity or
observation unavailability. Focused implementation and provider-sandbox acceptance are deferred to
the private-backend gate. This governance adds no schema or migration `20260808_0025` and keeps the
single Alembic head `20260808_0024`.

## ADR-134 private backend signature gate

The private implementation receives an explicit version-pinned accessor, fresh TLS-context
factory, zero-argument managed clock factory, and expected clock reference. Accessor results echo
the existing credential, operation purpose, and provisioning references and return one bounded
mutable buffer. No new version identity or public contract is introduced.

The later implementation must validate fresh SSL contexts, use one exact positive remaining
duration for every httpx timeout phase, disable environment trust, redirects, retries, and fallback,
and clean every request-local resource exactly once. Local HTTPS sandbox and PostgreSQL acceptance
follow implementation. This gate adds no schema or migration `20260808_0025`.

## Private backend implementation gate

The request-local private backend validates the version-pinned accessor's credential,
operation-purpose, and provisioning echoes, copies only bounded mutable secret material, and
erases both received and copied buffers. A fresh managed clock is read once, the exact positive
remaining duration bounds every HTTP phase, and a fresh verified TLS context constructs one
hardened `httpx.AsyncClient` with environment trust and redirects disabled. Provider-sandbox and
PostgreSQL acceptance remain separate; no live credential, provider, schema, or migration
`20260808_0025` is introduced.

## Local HTTPS provider-sandbox acceptance gate

**Status: Implemented / Validated, Pending Review.** The acceptance harness generates an ephemeral
localhost certificate outside the repository, starts a real loopback TLS server on the canonical
HTTPS endpoint, and drives delivery and observation through the production `httpx` transport.
Successful acknowledgement, exact idempotency carriage, timeout, disconnect, redirect, malformed
response, one-call bounds, and managed secret cleanup are verified. This is local synthetic
acceptance only; live credentials, provider traffic, deployment, schema, and migration
`20260808_0025` remain absent.

## PostgreSQL connector evidence acceptance gate

**Status: Implemented / Validated, Pending Review.** The gate persists one verified result produced
through the production connector and real loopback HTTPS transport, proves concurrent exact replay,
and verifies the serialized revision is identical to the authoritative result. The combined matrix
retains observation linkage, stale/substituted scope rejection, concurrency, and rollback residue
zero. PostgreSQL stores no secret, bearer header, or raw provider body; the Alembic head remains
`20260808_0024` and migration `20260808_0025` remains absent.

## Sprint 17 closeout

Sprint 17 is complete within the deployment-neutral boundary merged through PR #163 to PR #170.
The immutable operator manifest, exact construction-time validation, private request-local secret
accessor and HTTPS transport, trusted deadline clock, local TLS provider sandbox, and PostgreSQL
lifecycle/reconciliation evidence are implemented and validated. The authoritative CI at the final
acceptance head completed `2278` tests successfully.

This closeout does not enable a live connector. Production credential provisioning, secret-manager
vendor and workload identity selection, live endpoint traffic, process entrypoint/runbook,
controlled deployment, observation/rollback operations drill, tag, and release remain explicit
operator decisions. The next product step is a separately approved validation sprint using the
bounded local vertical slice. The Alembic head remains the single `20260808_0024` head; migration
`20260808_0025` is absent and no new authority, schema, or persistence owner is introduced.

## ADR-135 atomic handoff correction gate

The local validation sprint exposed a contract gap rather than a schema gap. A deliverable API
submission must stage one exact caller-supplied `RuntimeEffectAtomicWriteSet` in the facade-owned
transaction so base records, outbox, effect, `ENQUEUED` lifecycle, head, and transport receipt
commit or roll back together. Generic outbox rows are evidence only and are not converted or
backfilled. Execution projection and delivery lifecycle remain separate.

Public-contract correction, active-persistence PostgreSQL evidence, and resumed vertical
validation are separate gates. Live credentials, provider traffic, deployment, schema changes,
and migration `20260808_0025` remain prohibited.

## ADR-135 submission-stage public contracts

The Runtime API submission stage now accepts exactly one local-only `RuntimeAtomicWriteSet` with
no outbox or one complete caller-supplied `RuntimeEffectAtomicWriteSet`. A base outbox without its
matching initial-effect aggregate fails closed. Deliverable validation reuses the CP8 exact
effect, envelope, lifecycle-revision-one, receipt, transaction, scope, classification, lineage,
revision, digest, and time bindings before the base facts are compared with the API persistence
binding. Reconciliation, query non-mutation, facade signatures, and transaction ownership are
unchanged.

This contract-only gate performs no active-session effect persistence or PostgreSQL mutation.
Those behaviors and resumed vertical validation remain separately reviewed gates. The Alembic
head remains `20260808_0024`, and migration `20260808_0025` remains absent.

## ADR-135 active-session effect persistence and PostgreSQL atomicity

Active-transaction Persistence now accepts the closed deliverable stage and uses the same bounded
row-staging helper as the existing fresh-session effect transaction. The helper validates and
stages the exact base records, outbox, effect, lifecycle revision one, and lifecycle head without
owning a transaction or reading a clock. The facade-owned root transaction remains unchanged and
the existing idempotency layer stages the transport receipt in that same transaction.

Focused PostgreSQL evidence covers outer rollback residue zero, unchanged root-transaction
identity, pre-commit invisibility to Worker due selection, and complete `ENQUEUED` visibility
after commit. Existing fresh-session effect commit and replay behavior remains in the combined
regression. No schema, backfill, dispatcher, or migration `20260808_0025` is introduced.

## Gemini wire and local validation correction gate

**Status: Governed / Pending Review.** ADR-137 fixes the one approved Interactions endpoint,
revision header, typed `steps` response, storage/background denial, and strict transport-field
handling. A direct Draft 2020-12 `jsonschema` dependency owns bounded request-schema compilation
and local response validation before `ModelResponse` construction.

The subsequent implementation gate is network free and may add only the adapter, registry wiring,
dependency declaration, focused tests, architecture guard correction, and matching operations and
security documentation. It cannot add a provider SDK, schema persistence, migration
`20260808_0025`, live credentials, provider traffic, fallback, deployment, tag, or release.

## Gemini Interactions adapter implementation gate

**Status: Implemented / Validated, Pending Review.** The registry selects the Gemini adapter only
from exact deployment configuration and injects one explicit secret value, model, bounded timeout,
application retry policy, immutable public-only transmission policy, redactor, and optional audit
sink. Every invocation creates and closes one `trust_env=False`, redirect-disabled `httpx` client.

Request schemas are bounded, meta-validated, and compiled before client construction. Successful
responses require the pinned revision, exact model and response identity, one typed text output,
bounded integral usage, JSON decoding, and local Draft 2020-12 validation. Tests remain network
free. Live smoke, production credentials, provider traffic, deployment, schema changes, and
migration `20260808_0025` remain separately prohibited.

## Gemini documented optional response and safe diagnostic correction gate

**Status: Governed / Pending Review.** The approved live smoke consumed exactly one call and
returned safe `invalid_response` with retry zero. ADR-138 keeps the response profile closed while
governing optional `service_tier`, nullable cached/thought/tool usage counters, and one private
bounded structural rejection category. Raw response, prompt, schema fragments, provider messages,
and credentials remain unavailable to diagnostics.

Network-free adapter correction, CI review, and a separately approved second live smoke follow in
that order. This gate adds no production traffic, public contract, persistence, schema, or
migration `20260808_0025`.

## Gemini response wire and safe diagnostic correction

**Status: Implemented / Validated, Pending Review.** Network-free tests cover every allowed
`service_tier`, absent optional usage counters, missing required aggregate counters, malformed
usage, and bounded private rejection categories. The adapter performs no diagnostic retry and
does not expose provider values through the public error.

This correction adds no credential use, provider traffic, public contract, persistence, schema,
or migration `20260808_0025`. A second live smoke remains a separate approval gate.

## Gemini request-rejection safe diagnostic and wire-probe governance gate

**Status: Governed / Pending Review.** The second explicitly approved synthetic-public smoke used
one call, application retry zero, and no fallback, then returned safe `invalid_request`. ADR-139
does not infer the rejected field. It closes request diagnostics to HTTP 400 or 422 crossed with
`INVALID_ARGUMENT`, `FAILED_PRECONDITION`, `OUT_OF_RANGE`, the existing policy-block statuses, or
`unclassified`; provider values and arbitrary text are discarded.

The following implementation gate is network free and changes only the private request diagnostic
and the single structured-output `response_format` container to one exact array element. A later
live probe requires separate approval and must stop after exactly one call. Endpoint, revision,
model, schema, classification, credential, retry, and fallback substitutions are prohibited. This
gate adds no public contract, persistence, schema, or migration `20260808_0025`.

## Gemini request-wire and safe diagnostic correction gate

**Status: Implemented / Validated, Pending Review.** Network-free tests prove an exact one-element
`response_format` array, unchanged endpoint/revision/model/schema facts, and closed private
diagnostics for HTTP 400 and 422. The adapter recognizes only the ADR-139 provider-status allowlist
and collapses all missing, malformed, oversized, case-substituted, or unknown values to
`unclassified` without retaining provider content.

Public error and retry semantics remain unchanged. Credential use, provider traffic, a follow-up
probe, public contracts, persistence, schema, and migration `20260808_0025` remain outside this
gate. A single live probe still requires separate explicit approval after authoritative CI.

## Gemini API-version path governance gate

**Status: Governed / Merged.** ADR-140 governs a network-free path-only correction from
`/v1beta/interactions` to `/v1beta2/interactions`. The existing revision header and entire request
body remain unchanged so the next separately approved one-call probe has exactly one variable.

CI and tests must prove one literal path, no negotiation or fallback, one request, and unchanged
public error, classification, retry, client-lifetime, and local-validation behavior. This gate adds
no credential use, provider traffic, persistence, schema, or migration `20260808_0025`.

### Gemini API-version path correction implementation

**Status: Implemented / Validated, Pending Review.** The adapter and credential-free tests now pin
`/v1beta2/interactions` without changing any other request fact. A live probe remains separately
approved; persistence, schema, and migration `20260808_0025` remain absent.

## Gemini canonical path and HTTP-404 provenance governance gate

**Status: Governed / Merged.** ADR-141 selects `/v1/interactions` as the sole next path,
rejects model-only attribution of HTTP 404, and requires a network-free correction plus CI before
another separately approved one-call probe.

## Gemini canonical path and HTTP-404 diagnostic correction gate

**Status: Implemented / Validated, Pending Review.** The adapter now uses only
`/v1/interactions`; network-free tests reject `/v1beta`, `/v1beta2`, negotiation, and fallback.
HTTP 404 remains public non-retryable `configuration_error` with private category
`request_http_404_unclassified`, without provider detail or model-only provenance. No credential,
external call, public contract, persistence, schema, or migration `20260808_0025` is included. A
later one-call synthetic-public probe remains separately approved.
## Gemini logical model and provider wire resource governance gate

**Status: Governed / Pending Review.** ADR-142 assigns caller-visible authorization, lineage, and
audit identity to the exact logical `model_id`, and assigns request serialization plus provider
response-echo validation to a separately supplied exact provider wire resource. `models/` prefix
generation, stripping, alias resolution, registry-latest selection, response-derived replacement,
and fallback are prohibited.

The following correction gate is network free and may change only the explicitly approved config,
registry wiring, adapter, tests, and operational documentation needed to carry and compare both
facts. A later probe changes only the model resource and still requires separate one-call approval.
No schema, backfill, persistence change, or migration `20260808_0025` is introduced.

## Gemini registry snapshot and production composition governance gate

**Status: Governed / Pending Review.** ADR-143 requires application-factory injection of one
immutable `ModelRegistrySnapshot` and one exact logical selection. A pure binder returns the
selected active Gemini registration's logical `model_id` and exact `provider_model_name`.
Missing, stale, disabled, cross-provider, revision-mismatched, or substituted facts fail before
credential access or network I/O. Registry persistence, discovery, fallback, schema, and migration
`20260808_0025` remain prohibited.

## AI Office production dependency-bundle and route-composition governance gate

**Status: Governed / Validated, Pending Review.** ADR-144 requires one immutable AI Office bundle
at application construction. The application factory validates exact provider-mode cardinality,
binds the caller-supplied registry snapshot and logical selection, builds one office composition,
and gives it to an artifacts-router factory. Request-time settings lookup, gateway reconstruction,
mutable `app.state`, module-global registry state, synthetic snapshots, and first/latest selection
are prohibited.

Missing or partial Gemini dependencies fail construction before router publication, credential
access, or network I/O. A separately approved production correction gate may change the application
factory signature and internal route composition while preserving provider-neutral contracts,
Runtime facade signatures, HTTP payloads, the single Alembic head `20260808_0024`, and the absence
of migration `20260808_0025`.

## AI Office request-scoped gateway, audit and execution-composition governance gate

**Status: Governed / Validated, Pending Review.** ADR-145 narrows the application-lifetime object to
one secret-free `OfficeCompositionBlueprint` and an exact provider-bound request execution scope
factory. Gemini requires the factory, immutable registry snapshot and logical selection; OpenAI
requires only the factory; fake and disabled accept no external bundle and use only their reviewed
network-free factory.

For each work-package mutation, the artifacts route creates one request DB-bound
`ProviderAuditRepository`, enters one fresh managed execution composition, awaits the Office
operation and exits before the request session ends. The service receives the composition
explicitly and cannot read settings, build a gateway or select registry facts. A separately
approved production correction must remain network free and add no schema or migration
`20260808_0025`.
## AI Office production composition correction gate

Status: implemented locally, validation required before publication.

- The application factory accepts the optional AI Office dependency bundle explicitly while
  preserving the Runtime bundle's positional compatibility.
- Fake and disabled modes use reviewed network-free request factories. OpenAI and Gemini require
  exact external factory cardinality; Gemini additionally requires one exact immutable registry
  snapshot and logical selection.
- Work-package mutation creates one database-bound provider audit sink, enters one fresh managed
  execution composition, completes the application service operation, and exits exactly once.
- Artifact reads and reviews do not enter provider execution scope.
- No production credential, external provider call, PostgreSQL schema change, or migration
  `20260808_0025` is included.

## ADR-146 logical-result classification ownership governance gate

**Status: Governed / Validated, Pending Review.** PostgreSQL vertical acceptance exposed a real
contract/schema conflict rather than a fixture-only failure: an immutable `CONFIDENTIAL`
execution-request revision can legitimately own `RESTRICTED` state, audit, result, and effect
facts, while migration `20260808_0023` requires one shared FK classification.

ADR-146 assigns the request revision's exact source classification and the attempt's exact
effective classification to separate owners. The next public-contract gate adds explicit source
classification carriage; the following persistence gate implements fail-closed migration
`20260808_0025`. Existing vertical candidate work remains preserved and cannot resume until both
gates merge. This governance gate changes no production contract, schema, database row, provider,
credential, route, tag, or release.

## Logical-result source/effective classification public-contract gate

The public Runtime persistence contracts now require an explicit execution-request source
classification and retain the effective classification on state, audit, logical-result, effect,
and query scopes. Contract validation permits only equal or monotonic elevation and preserves both
facts through exact query reads. This checkpoint changes no persistence implementation, schema, or
migration; `20260808_0024` remains the single Alembic head pending the separately governed
`20260808_0025` gate.

## ADR-147 logical-result historical payload backfill governance gate

**Status: Governed / Validated, Pending Review.** Historical logical-result payloads cannot be
strictly deserialized after the source-classification contract amendment unless their immutable
JSON also receives the new authoritative field. ADR-147 assigns both the relational column and
canonical payload value to the same exact request-revision join.

The persistence gate must preflight the complete store before any change, reject collisions and
partial states, perform the bounded immutable rewrite and trigger restoration in one PostgreSQL
transaction, and prove relational/payload equality. Repository injection, best-effort repair,
populated downgrade, production changes, and migration creation remain outside this governance
checkpoint.

## Logical-result classification persistence gate

**Status: Implemented locally; validation pending.** The gate introduces the single governed
Alembic head `20260808_0025`, performs an exact historical source-classification backfill, and
changes the request/attempt uniqueness boundary so classification cannot hide duplicates.
Migration preflight covers missing or ambiguous request revisions, inconsistent history, lowered
classification, non-object payloads, and pre-existing canonical-field collisions before DDL.

Required acceptance includes fresh and populated PostgreSQL 16 upgrade, equal/raised binding,
trigger restoration, strict read mismatch rejection, replay/concurrency, rollback residue zero,
populated downgrade state preservation, empty downgrade, and the exact single head. No vertical-
slice candidate reuse, credential/provider access, tag, or release belongs to this checkpoint.

## Resumed Runtime vertical-slice validation gate

**Status: Implemented / Validated, Pending Review.** One deterministic PostgreSQL 16 scenario
crosses the actual HTTP submission route, trusted preparation pipeline, facade-owned root
transaction, active-session initial-effect persistence, committed due selection and synthetic
Worker delivery. The initial effect appears as exactly one `ENQUEUED` candidate only after commit;
the Worker records lifecycle revisions 2 through 4 and invokes the synthetic delivery capability
exactly once.

The HTTP replay returns the same safe execution projection, calls the authoritative submission
callback once in total and leaves one transport receipt and one four-revision delivery history.
Cross-tenant due selection returns no candidate. Execution projection and delivery lifecycle are
reported separately, and the combined acceptance matrix retains pre-commit invisibility and
conflict rollback residue zero. This gate uses the merged migration `20260808_0025`, adds no
further public contract, schema or migration, and performs no live provider call, deployment, tag
or release.
