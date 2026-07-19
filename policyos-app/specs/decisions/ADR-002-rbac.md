# ADR-002 — Organization-Scoped RBAC

## Status
Accepted

## Decision
Use memberships, roles, and atomic permissions. Permissions are evaluated within an organization context.

## Consequences
- A user may have different roles in different organizations.
- Permission checks require active membership resolution.
- UI visibility is not authorization.
