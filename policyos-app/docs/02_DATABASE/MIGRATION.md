# Migration Policy

1. Every schema change requires an Alembic revision.
2. Migration names must describe intent.
3. Destructive changes require a two-step migration when possible.
4. Backfills must be bounded and observable.
5. Migrations must be tested against a representative database.
6. Application deployment order must be documented for incompatible changes.
7. Downgrade logic is preferred but not allowed to create false safety; document irreversible migrations.

## Sprint 2 review
No new Sprint 2 migration is required. The existing foundation revision `20260718_0001_foundation_identity_rbac_audit.py` already creates `users.password_hash`, organizations, memberships, roles, permissions, role and membership link tables, and audit events. Sprint 2 authentication and authorization changes use those existing columns and relationships without changing schema.
