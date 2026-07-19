# EPIC-001 ??Authentication and Identity

## Status
Completed for Sprint 2

## Goal
Provide secure authentication and organization-scoped authorization.

## Existing foundation
Identity uses the existing `Organization`, `User`, `Membership`, `Role`, `Permission`, `RolePermission`, and `MembershipRole` models. Sprint 2 did not recreate or alter these models.

## Delivered
1. Argon2 password hashing and verification
2. Short-lived signed JWT access tokens with minimal claims
3. `POST /api/v1/auth/login`
4. `GET /api/v1/auth/me` and `get_current_user`
5. Active, tenant-safe organization membership resolution
6. Exact organization-scoped permission checks through `require_permission`
7. Login and authorization-denial audit hooks
8. Configuration validation for production JWT secrets
9. Unit, API, security, membership, RBAC, migration, and end-to-end regression tests

## Acceptance result
- Plain passwords are never stored or returned.
- Valid credentials return a signed access token.
- Invalid credentials return a generic `401` response.
- Expired, malformed, and incorrectly signed tokens are rejected.
- Protected endpoints resolve only active users.
- Cross-organization membership and role access is denied.
- Permission checks support exact atomic permission names and combine membership roles.
- Ruff and Pytest pass.

## Deferred
- Login rate-limit implementation, pending a shared gateway or middleware subsystem
- Refresh tokens, logout, and token revocation, pending persistent token lifecycle requirements
- Structured API-wide error envelopes and stable error codes
- Production issuer and audience configuration if deployment topology requires them
