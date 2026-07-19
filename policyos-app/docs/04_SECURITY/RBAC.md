# RBAC Policy

## Model
Permissions are exact, atomic capabilities. Roles group permissions, and active organization memberships receive roles through `MembershipRole`.

Examples:
- `policy.read`
- `policy.create`
- `policy.review`
- `policy.approve`
- `member.manage`
- `role.manage`
- `agent.execute`
- `audit.read`

## Enforcement flow
1. `get_current_user` validates the bearer token and active user.
2. `get_active_organization_context` resolves the active organization and the authenticated user's active membership.
3. `require_permission(permission_key)` joins `MembershipRole`, `Role`, `RolePermission`, and `Permission`.
4. The query requires the membership ID, the current organization ID on the role, and an exact permission key match.
5. Any matching role grants access, so permissions combine across multiple roles assigned to the same membership.

A role from another organization cannot grant access. Prefixes and wildcards are not implied: `policy.read.all` does not satisfy `policy.read`. System or organization-null roles are not treated as grants by the current organization-scoped check.

## Responses and audit
- Authentication failures return generic `401` responses.
- Missing or inaccessible organization contexts return the same `404` response to prevent tenant disclosure.
- Authenticated users lacking the exact permission receive `403 Permission denied`.
- Permission denials produce an `authorization.denied` audit event containing actor, membership, organization, and permission identifiers, but no token or request body.

UI visibility is never an authorization control. Enforcement belongs in FastAPI dependencies or the service layer.
