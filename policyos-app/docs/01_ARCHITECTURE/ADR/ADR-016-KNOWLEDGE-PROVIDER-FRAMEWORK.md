# ADR-016: Knowledge Provider Framework

Status: Accepted  
Date: 2026-07-25

## Context

Sprint 6 routed legal, minutes, finance, public-data, and internal queries directly to retrieval or
named MCP servers. Sprint 7 adds production connector configuration and persistence. Binding the
router directly to individual APIs or MCP tools would duplicate policy, error, evidence, fallback,
cache, health, and audit behavior and create provider lock-in.

## Decision

Introduce a provider-independent contract above transport-specific connectors. MCP, OpenAPI,
internal database, and internal knowledge adapters implement the same capability-driven protocol.
MCP is treated as a first-class transport through the existing governed gateway, not as an
arbitrary process or tool invocation surface.

Provider selection is organization-scoped, health- and capability-aware, and deterministic.
Fallback is explicit, bounded, audited, and prohibited for authentication, policy, classification,
security, and data-egress failures. Provider output is normalized into safe evidence. Raw provider
responses never cross the adapter boundary because they may contain secrets, executable
instructions, unstable schemas, or unnecessarily sensitive content.

The existing Knowledge Router remains compatible through an adapter while migration proceeds.
Existing `knowledge.read`, connector management, MCP execution, and classification policies are
reused rather than introducing broad new permissions.

## Consequences

- Provider-specific schemas and credentials remain behind adapters and configuration resolvers.
- Common selection, fallback, confidence, freshness, merge, cache, health, and audit policies are
  reusable and testable without network or subprocess execution.
- Provider implementation scores are not trusted as PolicyOS confidence.
- A provider factory can create only allowlisted adapter types.
- Additional adapters require mapping and validation work, but do not change router consumers.

Korean Law MCP, budget, court, council-minutes, filesystem, GitHub, and news providers can be added
incrementally. The Korean Law provider is intentionally deferred until its concrete server/tool
contract and fixtures are approved.
