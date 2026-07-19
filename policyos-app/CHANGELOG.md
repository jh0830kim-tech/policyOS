# Changelog

## Unreleased ??Sprint 2 authentication and identity
- Added Argon2 password hashing and constant-work credential verification.
- Added short-lived signed JWT access tokens with minimal `sub`, `iat`, `exp`, and `jti` claims.
- Added `POST /api/v1/auth/login` and authenticated `GET /api/v1/auth/me` endpoints.
- Added active organization membership resolution with tenant-safe `404` behavior.
- Added exact organization-scoped RBAC checks through membership roles and atomic permissions.
- Added login success, login failure, and authorization-denial audit events without sensitive request data.
- Added production JWT secret validation and a safe `.env.example` placeholder.
- Documented the login rate-limit integration point and deferred refresh-token and revocation design.
- Added end-to-end authentication and authorization regression coverage.

## 0.2.0 ??Documentation architecture
- Added PolicyOS Constitution.
- Added architecture, security, API, database, AI Office, and development guides.
- Added specifications for authentication, AI Office, and knowledge/RAG.
- Added agent and system prompt templates.
- Added ADR records and sprint-ready Codex prompts.

## 0.1.0
- Initial project documentation scaffold.
