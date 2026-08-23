# ADR-145: AI Office Request-Scoped Gateway, Audit, and Execution Composition Ownership

## Status

Accepted for the Sprint 17 AI Office request-scope composition governance correction.

## Context

ADR-144 requires application-construction validation and prohibits request-time registry discovery,
but its phrase "prebuilt office composition" is too broad for the existing provider lifecycle.
`OfficeComposition` contains agents that retain a gateway. A gateway retains a provider audit sink,
and production audit uses `ProviderAuditRepository(db)` bound to the request's `AsyncSession`.
Gemini also receives raw credential material and creates managed HTTP clients at its private
invocation boundary.

Keeping that gateway in an application-lifetime composition would retain a request database
session, audit sink, or credential beyond its authorized lifetime. Rebuilding from `Settings` in a
route would instead restore the second-authority problem that ADR-144 prohibits. Mutable
`app.state`, context globals, ambient sessions, and no-op production audit are not valid bridges.

## Decision

### Application-lifetime blueprint and bundle

ADR-144's application-lifetime object is narrowed to one immutable, secret-free
`OfficeCompositionBlueprint`. It contains only deterministic prompt definitions, agent and workflow
descriptors, the configured provider identity, and the exact logical/wire model binding already
validated at application construction. It contains no gateway, raw credential, provider client,
audit sink, database session, request, task, mutable registry, or cleanup callback.

The immutable `AIOfficeProductionDependencyBundle` has exactly these fields:

- `request_execution_scope_factory: OfficeRequestExecutionScopeFactory`;
- `model_registry_snapshot: ModelRegistrySnapshot | None`;
- `logical_model_id: str | None`.

For `gemini`, all three are required. The application factory runs ADR-143's pure binder and
requires the factory's immutable registry ID, registry revision, logical model ID, provider
instance ID, and provider wire-resource echoes to match the selected active registration exactly.
For `openai`, only the request-execution scope factory is present and both registry fields are
absent. For `fake` and `disabled`, the external bundle is absent and only the reviewed built-in
network-free factory is permitted. Extra, missing, ignored, cross-provider, or substituted bundle
fields fail application construction before router publication.

The bundle and factory may contain private capability references but cannot contain or expose raw
secret material. Credential materialization remains inside the managed request execution scope.

### Exact request-scope factory contract

`OfficeRequestExecutionScopeFactory` is an immutable, application-lifetime, provider-bound factory.
Its single operation has the conceptual signature:

```text
open(audit_sink: ProviderAuditSink)
  -> AsyncContextManager[OfficeExecutionComposition]
```

The factory is already bound to the construction-validated blueprint and exact provider/model
identity. It accepts no `Settings`, database session, registry snapshot, model selector, request,
credential value, URL, or fallback input. It creates a fresh managed execution composition for one
request and cannot be re-entered, reused across requests, or return a composition after exit.

`OfficeExecutionComposition` contains the request-scoped gateway, agent registry, workflow, and
prompt registry needed by one `OfficeApplicationService` execution. Its logical model and provider
identity must exactly equal the application blueprint. The scope owns provider credential
materialization, provider client lifetime, gateway lifetime, and reverse-order exactly-once cleanup.
Construction failure cleans every acquired resource exactly once and preserves the primary error.

### Audit and database-session ownership

The artifacts route owns no audit meaning. Its request `AsyncSession` creates exactly one
`ProviderAuditRepository(db)`, viewed only through the existing `ProviderAuditSink` Protocol. The
route enters the bound request execution scope with that sink, creates one
`OfficeApplicationService(db, execution_composition)`, awaits the complete work-package operation,
and exits the scope before the request database dependency ends.

The factory, gateway, and service cannot replace, cache, close, commit, roll back, or detach the
session. Existing `OfficeApplicationService` transaction behavior remains authoritative. A
provider audit write participates in that same request session and cannot be redirected to a
global, no-op, cross-request, or separately inferred sink.

### Router and service construction

The application factory validates and freezes the blueprint plus bound request-scope factory, then
passes them to an artifacts-router factory. The router captures only those immutable objects.
`OfficeApplicationService` requires one explicit `OfficeExecutionComposition`; it cannot accept
`Settings`, call `get_settings()`, call `build_office_composition()`, call
`create_model_gateway()`, or select a registry/provider/model.

Read-only artifact routes do not enter an execution scope. Only work-package mutation enters one
fresh scope exactly once. Authentication, organization, permission, idempotency, HTTP payloads,
safe error mapping, and the Runtime facade five-parameter signatures remain unchanged.

### Failure and non-disclosure

Missing, partial, stale, disabled, duplicate, revision-mismatched, identity-substituted, or
cross-provider construction facts fail before router publication. Missing or invalid request-scope
resources fail before provider network I/O. Raw credential, prompt, schema, provider response,
provider message, SQL detail, and internal factory error remain excluded from public errors, logs,
audit metadata, and persistence.

No provider fallback, latest lookup, synthetic snapshot, hidden UUID/time/reference, global
gateway, mutable `app.state`, ambient session, or production no-op audit is allowed.

## Schema and migration decision

The existing provider-audit table and request session are sufficient. This correction adds no
table, column, registry persistence, backfill, normalization, schema, or migration
`20260808_0025`. Alembic remains at the single head `20260808_0024`.

## Follow-up implementation boundary

A separately approved production correction may add the private bundle, blueprint and managed
scope contracts; change the application and artifacts-router factories; require explicit execution
composition in `OfficeApplicationService`; and update focused application, route, provider, and
architecture tests. It must remain network free and use synthetic credentials only.

## Rejected alternatives

- Retain a DB-bound audit sink or raw credential in an application-lifetime gateway.
- Rebuild the gateway from `Settings` inside each route or service.
- Put the current request session, audit repository, gateway, or secret in mutable `app.state`.
- Use a context global, ambient session, service locator, or production no-op audit sink.
- Let the request-scope factory select or repair registry/provider/model identity.
- Reuse one execution composition, credential, provider client, or gateway across requests.
- Add schema or migration `20260808_0025` for an application-lifetime correction.
