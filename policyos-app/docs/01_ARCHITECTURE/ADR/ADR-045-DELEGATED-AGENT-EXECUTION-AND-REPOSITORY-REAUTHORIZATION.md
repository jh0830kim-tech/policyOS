# ADR-045: Delegated Agent Execution and Repository Reauthorization

## Status

Accepted for Sprint 13 CP0.5.

## Decision

Every agent execution carries an immutable `on_behalf_of_user_id` together
with a distinct service actor and exact agent-instance identity. Delegation is
bound to one tenant, organization, task, resource, action, purpose, risk
level, classification, and bounded scope. Agent or service authentication
never creates independent administrator authority.

Delegated-user lineage is validated at model, MCP, connector, repository,
cross-validation, and Secretary handoff boundaries. A mismatch fails closed.

Repositories independently reauthorize the represented user and active
membership against the exact request and repository policy revision. Upstream
execution, model, MCP, connector, or task authorization does not imply
repository authorization. Repository permits are exact-request,
time-bounded metadata and are validated immediately before a provider-neutral
repository operation.

## Consequences

- Service identity and user authorization remain distinct.
- No delegated permissions are cached in a session.
- CP0.5 performs no database or repository operation.
- Existing Sprint 10–13 CP0 contracts remain unchanged.
