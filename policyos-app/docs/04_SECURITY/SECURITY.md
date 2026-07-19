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
