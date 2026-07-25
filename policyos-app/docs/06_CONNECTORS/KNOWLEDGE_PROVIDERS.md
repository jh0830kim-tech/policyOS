# Knowledge Provider Framework

Sprint 7 Checkpoint 3 introduces a provider-independent boundary between the Knowledge Router
and external or internal evidence systems. It does not connect a live Korean Law service.

## Contract

Every provider has a stable name, provider type, implementation version, explicit capabilities,
supported source types, organization scope, health state, priority, and optional fallback group.
Providers support only declared operations. Unsupported operations return a typed safe error.

Supported provider types are MCP, OpenAPI, internal database, internal knowledge, filesystem,
GitHub, search, and custom. The factory creates only allowlisted adapters; API callers cannot
select a Python class, MCP server, tool, command, endpoint, or transport.

## Selection and fallback

Selection filters by organization, enabled state, health, capability, source type, temporal
support, persistent-ingestion support, exclusions, and fallback group. Priority and provider name
provide deterministic tie-breaking. A preferred provider is used only when it satisfies policy.

Timeout, transient unavailability, rate limiting, disabled/capability failures, and configured
empty-result cases may fall back. Authentication, policy, classification, security, malformed
request, explicit provider-only, and data-egress denials never fall back. Attempts are bounded and
providers are never repeated.

## Trust boundary

MCP is a first-class provider transport but remains behind `GovernedMCPGateway`. The generic MCP
adapter maps PolicyOS operations only to configured allowlisted tools. Tool results are untrusted
data. Executable-looking instructions are warned about and are never executed. Raw responses,
credentials, commands, endpoints, and query strings are absent from provider responses and audit.

Restricted information cannot be sent to external providers. Confidential information requires
explicit external-transmission authorization. Internal retrieval preserves organization and
classification filtering.

## Evidence quality

Provider confidence is ignored. PolicyOS recalculates confidence from official-source status,
citation and identifier completeness, date consistency, temporal match, content completeness,
schema validity, provider health, and corroboration. Freshness considers retrieval/effective dates
and cache status without penalizing an official historical document merely for being old.

Merge removes duplicate resource IDs and content hashes, retains temporal conflicts with warnings,
prefers official authority, preserves provider counts, and uses deterministic ordering.

## Cache and audit

Cache keys include organization, provider/version, operation, hashes of query/resource/filter
inputs, source types, dates, top-k, and schema version. They exclude credentials, raw sensitive
queries, email, session IDs, and role lists.

Audit records contain request/correlation IDs, query hash, provider/type, capability, source types,
selection/fallback, safe counts, citation completeness, cache status, latency, outcome, error code,
classification, and policy decision. Raw query/evidence/response and secrets are prohibited.

## Current adapters

- `FakeKnowledgeProvider` variants for deterministic tests.
- `DisabledKnowledgeProvider` for explicit unavailable configuration.
- `InternalKnowledgeProviderAdapter` for existing governed retrieval.
- `GenericMcpKnowledgeProviderAdapter` skeleton for fake-gateway operation mappings.

Korean Law MCP mappings, live MCP/network transports, provider-specific schemas, and scheduled
persistent ingestion are deferred to a later checkpoint.

