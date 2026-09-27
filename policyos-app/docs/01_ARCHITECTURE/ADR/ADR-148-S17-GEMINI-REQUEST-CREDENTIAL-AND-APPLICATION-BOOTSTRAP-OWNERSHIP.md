# ADR-148: Gemini Request Credential and Application Bootstrap Ownership

## Status

Accepted governance; production implementation and live acceptance remain pending.

## Context

The merged application has an immutable AI Office bundle and request-scope Protocol, but
only fake/disabled built-in scopes. Settings currently requires and retains GEMINI_API_KEY,
and importing app.main eagerly constructs an application without injected dependencies.
These behaviors do not implement the approved request-local Gemini credential lifetime.
Local Runtime and HTTPS demo evidence is not live Gemini application-path evidence.

## Decision

### Credential authority and lifetime

A deployment-injected credential accessor is the sole production Gemini materialization
authority. The application retains only its private capability reference, never a raw key.
This supersedes ADR-136's Settings-owned construction-time key requirement for the future
injected production path. The accessor, not Settings, owns access to the deployment secret.
No ambient SDK discovery, GOOGLE_API_KEY fallback, second credential source, or request-
supplied credential is allowed. Existing legacy configuration remains unmodified in this
governance gate; it cannot be silently reused as the new production credential owner.

Validate the secret-free bundle and exact provider/logical/wire binding before credential
acquisition. Missing accessor fails application construction without reading a secret.
A missing, empty, whitespace-only or invalid credential fails scope entry before network
I/O; credentials must not be trimmed or repaired. The scope acquires a credential once,
creates a fresh gateway, and releases credential and gateway references on scope exit.
Success, failure, timeout, cancellation and partial construction all run reverse-order
exactly-once cleanup. Preserve the primary exception if cleanup also fails.
An exited scope cannot be re-entered and a retained execution handle must reject further
generation. No cross-request gateway, credential, client or audit-sink reuse is permitted.

Python string memory zeroization is not guaranteed. Reference release is a lifetime
guarantee, not proof of removal of all runtime or HTTP-library copies from memory.
Do not claim secure overwrite of immutable strings.

### Composition and bootstrap authority

Preserve AIOfficeProductionDependencyBundle's exact three fields:
request_execution_scope_factory, model_registry_snapshot, logical_model_id.
Preserve OfficeRequestExecutionScopeFactory.open(audit_sink) and the exact immutable
blueprint binding. The deployment accessor is a private dependency of the provider-bound
factory, not another public bundle field or a new request parameter.
The route supplies its existing request-bound ProviderAuditSink. No no-op production audit,
session replacement, transaction ownership transfer, or mutable app.state is allowed.

Separate the dependency-injected application factory from eager default ASGI construction.
Importing the injectable factory must not construct an external-provider application before
the deployment can supply its bundle. A compatibility default entry point may serve the
existing fake/disabled path; external provider selection without a bundle must fail closed,
not silently switch provider or expose a partially configured router. No import-time secret
read, provider call, environment mutation, or synthesized model registry is permitted.
The follow-up implementation must preserve existing route and facade signatures and test
default and injected startup independently. This ADR does not authorize a deployment.

### First live acceptance boundary

The first live validation is a separately approved PUBLIC synthetic single-agent call.
Exactly one provider call, application retry zero, transport retry zero, provider fallback
zero, store=false, background=false, and no tools or history are required. Work-package
execution is not the one-call entry point: existing workflows may execute multiple agents.
Full work-package validation requires separate approval. A failed or rejected call exhausts
the one-call budget; diagnostics cannot trigger a second request.

Preserve tenant, organization, permission, classification and lineage checks, exact logical/
wire model identity, local structured-output validation, bounded safe error mapping and
metadata-only audit. Do not print or persist credentials, prompts, structured context,
schemas, raw responses or arbitrary provider error messages. Success reporting is limited
to model, response ID, latency and token usage; failure reporting uses the existing safe
error code and closed private diagnostic category. No new diagnostic authority is added.

## Placement and dependency direction

The follow-up private scope/accessor composition belongs behind app.ai.production and the
existing provider adapter boundary; bootstrap belongs at the application entry point.
Domain/public gateway contracts cannot import deployment secret backends or application
composition. No vendor-specific secret backend or new adapter family is selected here.

## Validation matrix

Governance tests verify this decision and its cross-document links without reading secrets
or making network calls. Follow-up implementation tests must use synthetic accessors and
recording transports: construction validation before acquisition; zero calls on invalid
credentials; one acquisition per scope; success/error/cancellation/partial-construction
cleanup; primary-exception preservation; use-after-exit rejection; exact model and audit
binding; no secret disclosure; default/injected startup and existing route regression.
A separate live gate verifies one request only after offline validation and explicit approval.
PostgreSQL and Docker are unnecessary for this governance-only checkpoint.

## Schema and deferred work

Existing schema is unchanged; single Alembic head remains 20260808_0025.
No new migration, backfill or persistence ownership is introduced. ADR-146/147's already
merged classification migration is preserved, not prohibited retroactively.
Production code, exact private implementation signatures, entry-point file layout and their
exact test scope are a subsequent implementation Phase A, not claims of completed behavior.
Credentials, live traffic, publication, deployment, tag and release are not authorized here.

## Alternatives and consequences

Reject application-lifetime raw secrets, per-request Settings lookup, global gateways,
fallback discovery, bypassed audit and treating a multi-agent work package as one call.
The injected path requires offline implementation before any live result can be claimed.
Local demo remains usable independently; its execution projection and connector delivery
lifecycle remain separate authoritative results.
