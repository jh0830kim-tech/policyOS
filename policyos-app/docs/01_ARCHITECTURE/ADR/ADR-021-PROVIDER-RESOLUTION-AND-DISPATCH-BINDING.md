# ADR-021: Provider Resolution and Safe Dispatch Binding

## Status

Accepted for Sprint 8 Checkpoint 4.

## Context

The planner selects logical capabilities and the execution runtime emits immutable dispatch
requests. The system needs a deterministic way to choose a provider without importing live
providers, resolving credentials, probing health, or performing I/O. Sprint 7's knowledge
registry owns live provider instances and therefore is intentionally not the execution-domain
catalog.

## Decision

Introduce a pure provider resolution boundary in `app.execution.provider_resolution`:

- `ProviderDescriptor` and `ProviderCapability` contain only bounded, immutable, JSON-safe
  declarations. Provider identifiers are stable logical names, never endpoints or credentials.
- `ProviderCatalog` is explicitly constructed, immutable, duplicate-safe, and canonically
  ordered. It has no import-time registration or mutable global state.
- Availability is an immutable caller-supplied snapshot. Missing, stale, unavailable, and
  disabled states fail closed. Degraded and unknown states require explicit policy opt-in.
- `ProviderRequirement` is tied to dispatch, execution, step, tenant, actor, and classification
  scope. Preferred providers can come only from the trusted caller's requirement or policy.
- Eligibility is evaluated with stable reason codes. Ranking is lexicographic by trusted
  preference, availability, priority, reliability, latency, cost, and provider ID.
- `ProviderSelectionDecision` contains safe audit fields only. Required selection raises a typed
  failure when no provider is eligible; optional selection may be unbound with a warning.
- `DispatchBinding` revalidates dispatch, session, context, requirement, decision, catalog,
  classification, tenant, and deadline identities. It contains no input, credentials, endpoint,
  provider instance, or raw configuration.
- The Korean Law MCP integration is exposed as a static descriptor factory that records the
  Sprint 7 stable name as safe metadata but never imports or constructs the concrete provider.

All clocks, IDs, availability, policy, binding IDs, and idempotency keys are supplied by callers.
The resolver performs no network, database, cache, environment, secret, or provider operations.

## Consequences

Resolution is deterministic and replayable for the same explicit inputs. Candidate inspection
is linear in the bounded provider catalog and sorting is `O(P log P)`. Live provider invocation,
credential injection, retry handling, persistence, and result synthesis remain deferred to the
Checkpoint 5 executor boundary.
