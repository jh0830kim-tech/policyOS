# ADR-072: Runtime Adapter and External Invocation Architecture

## Status

Accepted for Sprint 15 CP0.

## Adapter families and contracts

`app.runtime.ports` defines the adapter input, bounded result-reference, typed error, capability,
timeout, cancellation, and invocation protocols. `app.runtime.adapters` will contain model,
provider, MCP, connector, internal-action, fake, and dry-run adapters. Fake and dry-run adapters
must precede real external adapters.

Each invocation binds an exact registry action/version, adapter/version, input/output schema
references, request, plan, step, attempt, tenant, organization, actor, agent, purpose, resource,
risk, classification, destination, authority, permit, idempotency key, timeout, retry eligibility,
and cancellation token/reference. The adapter validates this envelope but does not create policy.

## Invocation boundary

An adapter executes only after validated authority, permit, plan, registry binding, and READY or
RUNNING state. The permit is revalidated immediately before a side effect. The adapter cannot
broaden resource, action, purpose, tenant, organization, classification, destination, attempt, or
time scope. Adapter selection does not grant authority.

Adapters make no approval, authorization, permit, retry, compensation, publication, quarantine,
or release decision. They do not mutate Sprint 14 records and do not own API responses. Provider,
model, MCP, connector, and existing `app.execution` integrations are implementations behind the
port, not dependencies of runtime domain contracts.

Credentials are resolved at execution time through a tenant-bound credential broker reference.
Long-lived secrets, raw tokens, and credentials are never stored in immutable domain, plan,
state, audit, result, or outbox records and are never logged. Adapters return bounded result and
artifact references rather than unrestricted raw payloads where possible. Safe audit metadata
uses allowlisted fields and typed error codes.

Timeout and cancellation are cooperative boundaries and do not prove the external system stopped.
Retries require a new governed attempt. Destination enforcement includes exact endpoint/service
identity and rejects redirects or substitutions unless the registered action explicitly permits
them. MCP adapters additionally require the existing one-request MCP permit; repository actions
require the existing replay-protected repository permit.

## Consequences

External SDKs and transports remain replaceable infrastructure. The runtime can test authority,
state, idempotency, and audit behavior with fakes before enabling any real side effect.
