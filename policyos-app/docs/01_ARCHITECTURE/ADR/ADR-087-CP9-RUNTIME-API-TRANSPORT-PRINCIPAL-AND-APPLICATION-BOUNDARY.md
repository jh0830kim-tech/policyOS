# ADR-087: CP9 Runtime API Transport, Principal, and Application Boundary

- **Status:** Proposed
- **Date:** 2026-08-06

## Context

CP8 Runtime Delivery is complete. CP9 may expose a narrow HTTP transport, but authentication is not Runtime authority and all body, header, query, and path values are untrusted. Trusted issuer/audience and Runtime tenant binding are not yet established, so production routes remain blocked.

## Decision

Runtime routes and dependencies belong in `app.api`, transport schemas in `app.schemas`, and a trusted application facade/service sits between the API and Runtime Orchestration. Creating `app.runtime.api` is prohibited. Routes must not access ORM, Persistence, Adapter, provider, MCP, connector, or internal delivery APIs directly.

The server must use persisted/configured `Tenant-Organization` binding. Organization ID must never be assumed to be tenant ID. The authenticated principal must bind the trusted tenant and organization, active user or service principal, active membership, actor, optional agent, optional represented user, and classification context exactly. Production entry requires trusted JWT issuer and audience validation.

Exact permissions are `runtime.read`, `runtime.invoke`, and `runtime.reconcile`. Permission definition and role grant are separate; no wildcard or automatic grant is implied. Authentication, membership, or permission creates neither Authority nor execution authority.

Clients submit bounded commands and opaque references. They cannot inject Authority, Permit, Plan, State, Registry, Audit, Adapter, Persistence, credential, receipt, lifecycle, claim, lease, retry, dead-letter, identity, timestamp, or digest facts. The facade constructs trusted server-side facts and invokes existing Runtime boundaries.

Every invocation mutation requires an explicit bounded ASCII `Idempotency-Key`, scoped to tenant, organization, principal, operation, and command version. Exact replay returns the original safe response; a different command under the same key returns a typed conflict. This does not guarantee external business-effect exactly-once.

Requests require strict content types and schemas, bounded body and collection sizes, header limits, rate limits, timeouts, cancellation propagation, and safe correlation identifiers. Typed public error envelopes disclose no credentials, raw bodies, provider responses, internal exception details, SQL details, or cross-tenant existence.

Internal due selection, claim, lease, `DELIVERING`, lifecycle append, outcome commit, retry, dead-letter, receipt mutation, and direct Adapter operations are not public endpoints. CP9 enables no real provider/MCP/connector Adapter. Worker, queue, polling loop, scheduler, automatic retry, and redrive remain CP10 scope.

`CP9-Gate-API-Contracts` must define immutable principal, command/result, safe error, idempotency, and trusted facade contracts and merge with green CI before any production Runtime API route is implemented. Missing issuer/audience validation, Tenant-Organization binding, or stable facade contracts blocks CP9 production.

## Consequences

CP9 begins with a contracts gate. The transport remains thin, fail-closed, tenant- and organization-isolated, and unable to manufacture Runtime facts or bypass Orchestration.

## Alternatives rejected

- Treat organization ID as tenant ID: rejected because trusted binding is required.
- Accept Runtime facts from clients: rejected as authority and lifecycle injection.
- Let routes call Persistence or Adapters: rejected as a policy-boundary bypass.
- Create `app.runtime.api`: rejected because routes belong to `app.api`.
- Combine CP9 with Workers or real Adapters: rejected as CP10 and separately governed scope.
