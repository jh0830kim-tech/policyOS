# Core Table Dictionary

## organizations
Represents a council office, committee, public institution, or tenant.

## users
Stores user identity and account state. Password hashes only; never plain passwords.

## memberships
Connects users to organizations and carries organization-specific status.

## roles
Named authorization roles.

## permissions
Atomic capabilities such as `policy.read`, `policy.write`, or `admin.manage_members`.

## role_permissions
Many-to-many mapping between roles and permissions.

## membership_roles
Many-to-many mapping between organization membership and roles.

## policy_candidates
Stores policy ideas and their lifecycle state.

## audit_events
Planned table for actor, action, target, timestamp, organization, result, and metadata.
