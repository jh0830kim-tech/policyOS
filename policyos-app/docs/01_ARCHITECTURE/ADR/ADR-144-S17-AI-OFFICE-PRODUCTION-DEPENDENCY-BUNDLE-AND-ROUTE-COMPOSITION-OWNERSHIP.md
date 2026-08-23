# ADR-144: AI Office Production Dependency Bundle and Route Composition Ownership

## Status

Accepted for the Sprint 17 AI Office production-composition governance gate.

## Context

ADR-143 assigns the production application factory ownership of one immutable
`ModelRegistrySnapshot` and one exact logical model selection. The current AI Office path does not
provide a construction boundary that can carry those facts. `create_app()` includes a
module-global artifacts router, `OfficeApplicationService` rebuilds office composition from
`Settings` for each request, and `build_office_composition(settings)` has no registry input.

Adding registry state to mutable `app.state`, a module-global service locator, or request-time
settings would create a second authority and permit cross-request replacement. Synthesizing a
snapshot, selecting a first or latest registration, or letting the Gemini adapter repair the
missing binding would violate ADR-142 and ADR-143.

## Decision

### Immutable production dependency bundle

The application-construction caller owns one immutable AI Office production dependency bundle.
For Gemini, the bundle contains exactly one prevalidated `ModelRegistrySnapshot` and one exact
logical model selection, plus only the explicit factories needed to construct the governed office
composition. The bundle is secret free and contains no mutable registry, database session,
request, response, environment selector, provider client, credential, or service locator.

The application factory receives the bundle explicitly. It cannot read it from mutable
`app.state`, a module global, ambient environment selection, a first array entry, or a current or
latest persistence row. Missing or partial Gemini dependencies fail application construction
before the router is exposed, before credential access, and before network I/O.

Fake and OpenAI modes retain their existing explicit construction paths. They do not receive a
fabricated Gemini registry bundle, and their bundle cardinality is validated independently. A
Gemini bundle cannot be silently ignored in another provider mode, and another provider cannot
substitute for a missing Gemini bundle.

### Composition and route ownership

The application factory constructs one immutable office composition from the validated bundle and
passes it to an artifacts-router factory. The router factory closes over that exact composition;
it does not own registry selection, provider selection, settings lookup, gateway construction, or
request-local mutation.

`OfficeApplicationService` receives the prebuilt composition through explicit dependency
injection. It must not call `get_settings()`, `build_office_composition()`, or
`create_model_gateway()` during a request. Request handlers remain thin and cannot reconstruct,
replace, refresh, or discover the model registry or gateway.

The composition lifetime is application lifetime. Gemini's managed HTTP client and credential
remain request scoped inside the private gateway invocation boundary; they are not stored in the
application bundle or application-lifetime composition. The immutable registry snapshot may be
shared as inert application-construction authority but cannot be refreshed or mutated in place.

### Exact construction order and failure boundary

The only approved order is:

1. the deployment caller supplies settings, the immutable registry snapshot, and exact logical
   selection;
2. the application factory validates provider-mode bundle cardinality;
3. ADR-143's pure binder validates the exact active Gemini registration and wire resource;
4. the office composition and private gateway are constructed;
5. the artifacts-router factory receives that exact composition;
6. request handlers create an application service bound to that composition;
7. a request-scoped provider invocation may acquire its credential and client.

Missing, stale, disabled, duplicate, substituted, revision-mismatched, or cross-provider registry
facts fail closed at construction. There is no generic endpoint-time fallback from invalid
application construction to a bounded 503 because the application must not start with a partial
bundle. Runtime operational 503 semantics do not authorize an AI Office configuration fallback.

### Contract and schema boundary

This governance gate changes no production or public Python. A separately approved correction gate
may amend the exported application-factory signature, introduce the immutable internal bundle and
router factory, and update focused construction and route tests. The existing provider-neutral
`ModelRequest`, `ModelResponse`, normalized invocation contracts, Runtime facade five-parameter
signatures, and public HTTP payloads remain unchanged.

No registry serialization, persistence lookup, table, column, backfill, normalization, schema, or
migration `20260808_0025` is required. Alembic remains at the single head `20260808_0024`.

## Validation requirements for the correction gate

- Gemini construction succeeds only with one exact immutable snapshot and logical selection.
- Missing, partial, extra, stale, disabled, duplicate, substituted, or cross-provider facts fail
  before router publication, credential access, and network I/O.
- Fake and OpenAI construction enforce their own exact bundle cardinality.
- The artifacts router and `OfficeApplicationService` use one prebuilt composition and perform no
  settings, registry, or gateway reconstruction per request.
- Mutable `app.state`, module-global registry/service state, synthetic snapshots, and first/latest
  lookup are absent.
- Provider-neutral contracts, Runtime facade signatures, route payloads, Alembic head, and
  network-free test behavior remain unchanged.

## Rejected alternatives

- Store the registry snapshot or office service in mutable `app.state`.
- Keep the module-global router and let each request rebuild composition from `Settings`.
- Create a synthetic registry snapshot from `GEMINI_MODEL` or provider response fields.
- Select the first, current, or latest model registration.
- Treat missing Gemini composition as an endpoint-time fallback or substitute another provider.
- Put a request-scoped credential or provider client in the application-lifetime bundle.
- Add registry persistence or migration `20260808_0025` for this construction-only boundary.

## ADR-145 request-scope correction

The phrase "prebuilt office composition" in this ADR means a prevalidated, secret-free immutable
`OfficeCompositionBlueprint` plus one exact provider-bound request execution scope factory. It does
not authorize an application-lifetime gateway, raw credential, provider client, DB session or
audit sink. ADR-145 defines the exact bundle fields, provider-mode cardinality, managed factory
signature and request-scope audit ownership required before production correction.
