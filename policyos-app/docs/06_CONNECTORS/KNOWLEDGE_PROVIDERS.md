# Knowledge Providers

This document is the authoritative operational overview for the PolicyOS Knowledge Provider framework and its first concrete provider, Korean Law MCP. Architecture decisions are recorded in [ADR-016](../01_ARCHITECTURE/ADR/ADR-016-KNOWLEDGE-PROVIDER-FRAMEWORK.md) and [ADR-017](../01_ARCHITECTURE/ADR/ADR-017-KOREAN-LAW-MCP-PROVIDER.md).

## Framework boundary

A provider has a stable name and type, explicit capabilities and source types, organization scope, health, priority, and an optional fallback group. Selection is deterministic and filters disabled, unhealthy, out-of-scope, or unsupported providers before execution. API callers cannot choose Python classes, MCP tool names, commands, endpoints, credentials, or transports.

The Korean Law flow is:

```text
Knowledge Router
  -> Provider Registry / Selector
  -> Korean Law Runtime
  -> Request Translator
  -> Tool Registry / Capability Resolver
  -> Request Builder
  -> governed MCP Gateway boundary
  -> Response Validator
  -> Legal Normalizer
  -> KnowledgeEvidence
```

The Router knows only the `LAW_MCP` route and provider contracts. It does not know MCP tool names. The legal normalizer does not access the gateway, and the tool registry contains no credential or transport implementation. Runtime dependencies are injected; there is no mutable global provider runtime. Importing the package performs no configuration read, network request, subprocess execution, or gateway call.

## Korean Law MCP provider

- Provider name: `korean-law-mcp`
- Provider type: `mcp`
- Fallback group: `legal-official`
- Default state: disabled
- Source types: `law`, `case`, `administrative_rule`, `local_ordinance`, `legal_interpretation`
- Framework capabilities: `search`, `retrieve`, `history`, `compare`, `relationship_graph`
- Provider operations: `search_laws`, `get_legal_resource`, `search_cases`, `search_administrative_rules`, `search_local_ordinances`, `search_legal_interpretations`, `get_article_history`, `compare_versions`, `explore_legal_chain`

The central tool registry is the only default tool-name allowlist. A request cannot supply a tool name. Configured capabilities are unverified until discovery is supplied. Missing discovered tools remove their operations; missing required tools degrade or make health unavailable. No unsupported operation receives a fabricated result.

## Configuration

`KoreanLawProviderConfiguration` is a secret-free contract:

| Field | Meaning |
| --- | --- |
| `enabled` | Enables registration/runtime construction; defaults to `false`. |
| `server_name` | Stable MCP server identifier; defaults to `korean-law-mcp`. |
| `transport` | Configuration label: `disabled`, `remote`, or `local_process`; this checkpoint constructs no transport. |
| `credential_reference` | Optional identifier matching `env:NAME`; never the credential value. |
| `timeout_seconds` / `max_retries` | Bounded execution policy inputs. |
| `cache_enabled` / `cache_ttl_seconds` | Cache policy inputs; no provider-specific cache is implemented here. |
| `max_results` | Validated maximum normalized item count. |
| `implementation_version`, `priority` | Registration metadata and deterministic selection priority. |
| `organization_id` | Optional tenant scope. |
| `configuration_reference` | Non-secret connector configuration identifier. |

Configuration validation and local health are implemented. Credential resolution, environment-variable reads, remote health checks, live transport construction, and MCP discovery calls belong to the deployment composition boundary and are not implemented in this checkpoint.

## Trust and security boundary

MCP responses are untrusted until schema, size, item count, source type, identifier, URL, metadata, and nesting checks pass. Private/non-global URLs, scripts, credential-like values, internal Windows/Unix paths, forbidden metadata keys, and oversized responses are rejected. Prompt or command-like instructions are retained only as inert evidence data with warnings; they are never executed.

Provider results and audits contain neither raw MCP responses nor full legal text. Audit stores a SHA-256 query hash, query character count, safe identifiers/counts, status, warning/error codes, and timing. It does not store the full query, credential reference, exception cause, traceback, prompt, or raw response.

Restricted information is not sent externally. Confidential transmission requires the existing explicit authorization. Existing organization, membership, RBAC, MCP execution, and classification contracts are reused.

## Legal normalization and evidence integrity

Validated items become typed `LegalResource` variants and then standard `KnowledgeEvidence`. PolicyOS builds citations for laws, cases, administrative rules, local ordinances, and legal interpretations. Temporal metadata tracks effective, decision, proclamation, and retrieval dates, current version, temporal match, and warnings.

Confidence is recalculated from official authority, citation, identifier, date, and schema completeness; external MCP scores are ignored. Freshness derives from effective/retrieval dates and cache state. Canonical identifier plus version drives deduplication, so distinct versions of one resource remain available. Ordering and `top_k` enforcement are deterministic. Excerpts are bounded, content hashes are stable, and only validated allowlisted metadata crosses the trust boundary.

## Errors, retries, and fallback

| Condition | Result | Retry | Fallback |
| --- | --- | --- | --- |
| Invalid request / unsupported operation | typed rejection | no | no |
| Unavailable tool | unavailable | no unless represented as transient gateway failure | no |
| Timeout / rate limit / transient provider unavailable | unavailable | yes | yes when caller allows |
| Authentication / misconfiguration | failed or construction rejection | no | no |
| Malformed / oversized response / security violation | failed | no | no |
| Resource not found | successful empty/not-found result | no | no |

Only safe error codes/messages cross the boundary; raw exception text is not returned. Fallback is eligibility metadata for the existing bounded Router/provider policy, not an unbounded retry loop inside this provider.

## Router and testing

`KoreanLawKnowledgeRouterExecutor` adapts the existing `KnowledgeRouterService` `LAW_MCP` route to the provider execution service. It does not introduce a parallel router. The fake gateway is an explicitly injected deterministic test double and is never a production default. Ordinary tests perform no network or MCP subprocess execution.

Persistent ingestion is intentionally not implemented. The runtime exposes only a future boundary; it does not write to the database.

## Follow-up work for live operation

Before production enablement, implement deployment-owned credential resolution, governed transport composition, real tool discovery/version compatibility, remote health checks, operational cache/retry wiring, observability, and administrator configuration. Persistent ingestion requires a separate governed design and migration. These omissions must not be described as implemented capabilities.