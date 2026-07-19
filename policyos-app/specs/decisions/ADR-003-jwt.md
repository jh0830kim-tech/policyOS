# ADR-003 ??Signed JWT Access Tokens

## Status
Accepted for Sprint 2

## Decision
Use short-lived signed JWT access tokens for API authentication.

## Constraints
- minimal claims (`sub`, `iat`, `exp`, and `jti` only)
- server-side membership and permission lookup
- configurable algorithm and expiry
- secrets of at least 32 bytes outside local development and test environments

## Refresh and logout decision
Access-token-only authentication is sufficient for the current MVP because tokens expire after a short configured lifetime and the architecture has no token persistence, refresh-token store, or revocation subsystem. Adding refresh or logout now would imply durable token-family state and new operational security responsibilities without an established persistence design.

Refresh tokens and server-side revocation remain deferred. Revisit this decision when longer-lived sessions, compromised-token invalidation, or managed user sign-out become product requirements. Until then, clients discard access tokens locally and authorization continues to resolve memberships and permissions from trusted storage on every request.
