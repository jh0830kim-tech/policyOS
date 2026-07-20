# Security Baseline

## Security goals
- Protect credentials and personal data.
- Enforce organization isolation.
- Prevent unauthorized agent and tool access.
- Maintain reliable audit trails.
- Support incident response.

## Minimum controls
- Argon2 password hashing
- signed JWT access tokens
- short token lifetime
- RBAC authorization
- secret management through environment or secret store
- input validation
- rate limiting for authentication endpoints
- audit logging for privileged actions
- dependency and vulnerability monitoring

## Prohibited
- plain-text passwords
- secrets in source control
- authorization based only on UI visibility
- agent access to unrestricted organization data

## Login rate-limiting integration point
Login rate limiting must run before credential verification, preferably at the API gateway or as a dedicated FastAPI dependency on `POST /api/v1/auth/login`. The limiter should key conservatively on source network and a privacy-preserving account identifier, return `429` without revealing account existence, and emit operational metrics. Redis-backed limiting is deferred until PolicyOS establishes a shared rate-limit subsystem; individual routes must not create ad hoc Redis policies.
## Operational artifact controls
External-facing drafts remain `needs_review` until an authorized user with `artifact.review` approves or rejects them. All artifact and package reads are organization-scoped. Raw provider responses, secrets, and hidden reasoning are prohibited from persistence and API responses.

## External AI provider controls

Every real-provider request carries organization, user, task, and data-classification context.
Restricted data is denied. Confidential data requires an explicit organization policy or scoped
approval; public and internal data may proceed only when the organization allows the provider,
the caller has `agent.execute`, the tenant context matches, and the provider is approved. Policy
denials use the safe `provider_policy_blocked` code and do not expose provider or policy internals.
Provider audit APIs are not exposed to ordinary users. Any future audit read endpoint must require
an audit/admin permission and enforce organization scoping.

## Production workflow authorization

The Work Package router delegates execution only after authentication, active-membership resolution,
and exact `agent.execute` authorization. The application service receives the resolved organization
and user identifiers and uses them for every task, run, package, artifact, audit, and provider
transmission context. Read/review routes retain organization predicates. Provider failures are mapped
to allowlisted codes and messages without exposing SDK exceptions or stack traces.
## Secure document ingestion

Uploads are checked for allowed extension and MIME pairing, configured byte limit, empty content, normalized filename, traversal, executable/script suffixes, executable signatures, and extension/content magic before parsing. SHA-256 duplicate detection is scoped to organization and source. Malware scanning is an injected protocol and always runs before parser execution; production ingestion fails closed until a real scanner adapter is configured. HWP/HWPX are explicitly unsupported, encrypted or textless PDFs fail safely, embedded DOCX objects are rejected, spreadsheet formulas are never executed, and row/column limits constrain tabular parsers. Temporary files use a configured private directory and are removed on success or failure.
## Chunk and citation isolation

Chunk organization and classification are inherited only from the persisted document version; callers cannot downgrade them. Version, document, source, chunk, and citation queries include organization predicates and composite tenant foreign keys. Restricted chunks remain local and are not transmitted to providers. Chunk hashes, strategy/config hashes, and source block ranges make overlap and repeated processing auditable without inventing source pages, sections, or dates.
