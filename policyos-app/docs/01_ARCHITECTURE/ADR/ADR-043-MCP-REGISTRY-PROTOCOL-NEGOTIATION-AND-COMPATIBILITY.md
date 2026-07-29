# ADR-043: MCP Registry, Protocol Negotiation, and Compatibility Governance

Status: Accepted for Sprint 13 CP0

PolicyOS uses provider-neutral, immutable MCP server and tool registrations in revisioned snapshots. Registrations contain safe endpoint and credential references, never secrets. Protocol versions are exact opaque identifiers; resolution requires an explicitly requested common version and performs no automatic latest selection or upgrade.

Static declared, verified, and required capabilities remain distinct from runtime negotiated capabilities. Extension declarations are bounded and versioned. Negotiation results retain exact lineage without credentials, sessions, or tenant authorization.

The Korean Law implementation is frozen as legacy. vNext requires a distinct deployment identity and may coexist with legacy. Metadata-only contract tests and explicit migration gates precede shadow, canary, and current status. Gates represent decisions only; CP0 never changes aliases or deploys transports.
