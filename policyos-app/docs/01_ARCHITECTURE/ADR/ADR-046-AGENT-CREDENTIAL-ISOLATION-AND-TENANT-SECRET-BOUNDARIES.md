# ADR-046: Agent Credential Isolation and Tenant Secret Boundaries

## Status

Accepted for Sprint 13 CP0.5.

## Decision

Long-lived secrets remain behind a secret-broker boundary and are represented
only by tenant-scoped metadata references. Each reference binds to a tenant,
organization, service, revision, and tenant-specific encryption-key
reference.

Ephemeral grants bind to one exact tenant, agent instance, task, service,
scope, target, and bounded lifetime. Terminated, expired, or quarantined
agents cannot receive or validate grants. Grants cannot be shared across
agents, tasks, organizations, or tenants. Completion consumes or revokes
grants, and retries require new agent and grant identities.

All secret access is represented by immutable metadata-only audit records.

## Consequences

- Agents never receive long-lived secret values.
- CP0.5 does not resolve environment credentials, decrypt secrets, mint
  tokens, or integrate a cloud vault.
- Secret and audit contracts cannot contain credential payloads.
