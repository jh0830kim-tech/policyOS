# ADR-017: Korean Law MCP as a Knowledge Provider

Status: Accepted

Date: 2026-07-25

## Context

PolicyOS needs official Korean legal evidence without coupling the Knowledge Router or core legal
domain to one MCP server implementation. Direct connector calls would expose transport and tool
details to callers, duplicate selection and fallback policy, and allow untrusted provider output
to cross the evidence boundary.

## Decision

Integrate Korean Law MCP as the first concrete implementation of the existing Knowledge Provider
framework. MCP remains a transport/integration boundary below the provider adapter, rather than a
core-domain dependency.

- The provider is named `korean-law-mcp`, has type `mcp`, and is disabled by default.
- PolicyOS operations map to configured tool names only in a central allowlist registry.
- Configured capabilities remain unverified until tool discovery is supplied. Missing tools are
  unavailable; the provider never fabricates capability or evidence.
- A governed gateway is injected into the runtime. Importing or constructing domain configuration
  does not start a transport, network connection, or subprocess.
- Raw MCP responses are validated at the trust boundary before legal normalization.
- PolicyOS constructs citations, temporal status, confidence, and freshness. External scores are
  not used as PolicyOS confidence.
- The existing Knowledge Router, Registry, Selector, RBAC, classification, audit, and fallback
  contracts are reused.
- Deterministic tests inject a fake gateway; it is not a production default.
- Persistent ingestion is separate and remains unimplemented.

## Alternatives considered

### Call Korean Law MCP directly from the Router

Rejected because it would expose tool names and server-specific schemas above the provider
boundary and create a second selection/error/audit implementation.

### Add Korean Law details to the core provider domain

Rejected because provider-independent types must remain reusable by OpenAPI, internal, and future
knowledge sources.

### Trust MCP scores and citations

Rejected because external scores have unknown semantics and provider citations or dates may be
incomplete or inconsistent. PolicyOS must validate and recalculate evidence properties.

### Persist every result during execution

Rejected because query-time evidence and durable ingestion have different authorization,
retention, deduplication, migration, and audit requirements.

## Consequences

The design adds explicit translation, discovery, validation, normalization, and adapter layers,
but keeps dependencies one-directional and independently testable. A live deployment must supply
credential resolution, a governed transport/gateway, discovery, and health composition. Until
then, the provider remains disabled and tests remain network-free.

Tool changes are localized to configuration/registry mapping. Server schema changes fail closed
at response validation. Multiple legal versions can be retained while exact canonical-version
duplicates are removed.

## Security implications

Callers cannot choose tools, commands, URLs, credentials, or transports. Credential configuration
stores only an `env:NAME` reference identifier. Private URLs, scripts, credential-like content,
internal paths, forbidden metadata, excessive nesting, and oversized responses are rejected.
Prompt-like text remains inert data and produces warnings.

Raw response content, full queries, legal documents, exception causes, and credential references
are excluded from execution results and audit metadata. Retries and fallback are limited to
transient timeout, rate-limit, and availability failures; authentication, malformed response,
security, and invalid-request failures are not retried.

## Follow-up work

- Compose a production governed MCP transport and credential resolver.
- Verify actual server tool names and minimum versions through discovery.
- Add remote health checks and operational cache/retry telemetry.
- Extend Router task taxonomy for administrative rules and legal interpretations.
- Design persistent ingestion, retention, and migrations separately.
