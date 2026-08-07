"""Add the lifetime tenant-to-organization binding."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_0018"
down_revision: str | None = "20260805_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "tenant_organization_bindings"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_tenant_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("classification_ceiling", sa.String(length=20), nullable=False),
        sa.Column("provisioning_reference", sa.String(length=200), nullable=False),
        sa.Column("provisioned_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'revoked')",
            name="ck_tenant_org_binding_status",
        ),
        sa.CheckConstraint(
            "classification_ceiling IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_tenant_org_binding_classification",
        ),
        sa.CheckConstraint(
            "char_length(provisioning_reference) BETWEEN 1 AND 200 "
            "AND provisioning_reference = btrim(provisioning_reference)",
            name="ck_tenant_org_binding_provisioning_reference",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_tenant_org_binding_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["provisioned_by_user_id"],
            ["users.id"],
            name="fk_tenant_org_binding_provisioned_by_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_tenant_org_binding_organization"),
        sa.UniqueConstraint("runtime_tenant_id", name="uq_tenant_org_binding_tenant"),
    )


def downgrade() -> None:
    populated = op.get_bind().execute(sa.text(f"SELECT 1 FROM {_TABLE} LIMIT 1")).first()
    if populated is not None:
        raise RuntimeError("cannot remove populated tenant-organization bindings")
    op.drop_table(_TABLE)
