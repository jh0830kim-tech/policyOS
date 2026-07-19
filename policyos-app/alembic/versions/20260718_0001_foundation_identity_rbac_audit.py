"""Foundation identity, RBAC, audit events, and policy candidates.

Revision ID: 20260718_0001
Revises:
Create Date: 2026-07-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260718_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_ROLE_ID = "00000000-0000-0000-0000-000000000101"
ANALYST_ROLE_ID = "00000000-0000-0000-0000-000000000102"
PERMISSION_IDS = {
    "organization:manage": "00000000-0000-0000-0000-000000001001",
    "membership:manage": "00000000-0000-0000-0000-000000001002",
    "rbac:manage": "00000000-0000-0000-0000-000000001003",
    "audit:read": "00000000-0000-0000-0000-000000001004",
    "policy_candidate:read": "00000000-0000-0000-0000-000000001005",
    "policy_candidate:create": "00000000-0000-0000-0000-000000001006",
}


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=False)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_service_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "memberships",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_memberships_org_user"),
    )
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"], unique=False)
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"], unique=False)
    op.create_index("ix_memberships_org_status", "memberships", ["organization_id", "status"], unique=False)

    op.create_table(
        "permissions",
        sa.Column("key", sa.String(length=150), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_permissions_key"),
    )
    op.create_index("ix_permissions_key", "permissions", ["key"], unique=False)

    op.create_table(
        "roles",
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_roles_org_key"),
    )
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"], unique=False)
    op.create_index("ix_roles_key", "roles", ["key"], unique=False)

    op.create_table(
        "membership_roles",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("membership_id", "role_id"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "policy_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("candidate_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="idea"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_candidates_organization_id", "policy_candidates", ["organization_id"], unique=False)
    op.create_index("ix_policy_candidates_title", "policy_candidates", ["title"], unique=False)
    op.create_index("ix_policy_candidates_candidate_type", "policy_candidates", ["candidate_type"], unique=False)
    op.create_index("ix_policy_candidates_status", "policy_candidates", ["status"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_membership_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=150), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=40), nullable=False, server_default="success"),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["actor_membership_id"], ["memberships.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "actor_user_id", "actor_membership_id", "event_type", "resource_type", "resource_id", "request_id", "created_at"):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column], unique=False)
    op.create_index("ix_audit_events_org_created", "audit_events", ["organization_id", "created_at"], unique=False)
    op.create_index("ix_audit_events_resource", "audit_events", ["resource_type", "resource_id"], unique=False)

    organizations = sa.table(
        "organizations",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
    )
    roles = sa.table(
        "roles",
        sa.column("id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_system", sa.Boolean()),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )

    op.bulk_insert(organizations, [{"id": SYSTEM_ORG_ID, "name": "PolicyOS 기본 조직", "slug": "policyos", "is_active": True}])
    permission_rows = [
        {"id": permission_id, "key": key, "name": key, "description": f"Built-in permission: {key}"}
        for key, permission_id in PERMISSION_IDS.items()
    ]
    op.bulk_insert(permissions, permission_rows)
    op.bulk_insert(
        roles,
        [
            {"id": ADMIN_ROLE_ID, "organization_id": SYSTEM_ORG_ID, "key": "admin", "name": "관리자", "description": "조직 전체 관리 권한", "is_system": True},
            {"id": ANALYST_ROLE_ID, "organization_id": SYSTEM_ORG_ID, "key": "policy_analyst", "name": "정책연구관", "description": "정책 후보 조회 및 생성", "is_system": True},
        ],
    )
    op.bulk_insert(
        role_permissions,
        [
            *({"role_id": ADMIN_ROLE_ID, "permission_id": permission_id} for permission_id in PERMISSION_IDS.values()),
            {"role_id": ANALYST_ROLE_ID, "permission_id": PERMISSION_IDS["policy_candidate:read"]},
            {"role_id": ANALYST_ROLE_ID, "permission_id": PERMISSION_IDS["policy_candidate:create"]},
        ],
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("policy_candidates")
    op.drop_table("role_permissions")
    op.drop_table("membership_roles")
    op.drop_table("roles")
    op.drop_table("permissions")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")
