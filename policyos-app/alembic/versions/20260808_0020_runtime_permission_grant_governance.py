"""Add governed Runtime permission grant evidence and management definition."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0020"
down_revision: str | None = "20260807_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
_MANAGE_ID = UUID("00000000-0000-0000-0000-000000001904")
_MANAGED_IDS = tuple(
    UUID(f"00000000-0000-0000-0000-{value:012d}") for value in (1901, 1902, 1903, 1904)
)
_FIXED_TIME = datetime(2026, 8, 8, tzinfo=UTC)
_MANAGE = (
    _MANAGE_ID,
    "runtime.grant.manage",
    "Runtime grant management",
    "Manage governed Runtime permission grants.",
)


def _permissions() -> sa.Table:
    return sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def _grant_count(bind: sa.Connection) -> int:
    links = sa.table("role_permissions", sa.column("permission_id", sa.Uuid()))
    return int(
        bind.scalar(
            sa.select(sa.func.count())
            .select_from(links)
            .where(links.c.permission_id.in_(_MANAGED_IDS))
        )
        or 0
    )


def _manage_rows(bind: sa.Connection, table: sa.Table) -> list[sa.RowMapping]:
    return list(
        bind.execute(
            sa.select(table.c.id, table.c.key, table.c.name, table.c.description).where(
                sa.or_(table.c.id == _MANAGE_ID, table.c.key == _MANAGE[1])
            )
        ).mappings()
    )


def _exact(row: sa.RowMapping) -> bool:
    return (row["id"], row["key"], row["name"], row["description"]) == _MANAGE


def upgrade() -> None:
    bind = op.get_bind()
    table = _permissions()
    if _grant_count(bind):
        raise RuntimeError("Existing Runtime permission grants prohibit governance upgrade")
    rows = _manage_rows(bind, table)
    if rows and (len(rows) != 1 or not _exact(rows[0])):
        raise RuntimeError("Runtime grant management permission collision")

    op.create_unique_constraint(
        "uq_tenant_org_binding_scope",
        "tenant_organization_bindings",
        ["runtime_tenant_id", "organization_id"],
    )
    op.create_unique_constraint(
        "uq_memberships_actor_scope", "memberships", ["id", "user_id", "organization_id"]
    )
    op.create_unique_constraint("uq_roles_id_organization", "roles", ["id", "organization_id"])
    op.create_table(
        "runtime_permission_grant_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("actor_principal_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_membership_id", sa.Uuid(), nullable=False),
        sa.Column("target_role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(10), nullable=False),
        sa.Column("reason_reference", sa.String(200), nullable=False),
        sa.Column("provenance_reference", sa.String(200), nullable=False),
        sa.Column("classification_ceiling", sa.String(20), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_digest", sa.String(200), nullable=False),
        sa.Column("command_version", sa.String(40), nullable=False),
        sa.Column("prior_active", sa.Boolean(), nullable=False),
        sa.Column("resulting_active", sa.Boolean(), nullable=False),
        sa.Column("grant_revision", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("request_id", name="uq_runtime_grant_event_request"),
        sa.UniqueConstraint("receipt_id", name="uq_runtime_grant_event_receipt"),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "target_role_id",
            "permission_id",
            "grant_revision",
            name="uq_runtime_grant_event_target_revision",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "organization_id"],
            [
                "tenant_organization_bindings.runtime_tenant_id",
                "tenant_organization_bindings.organization_id",
            ],
            ondelete="RESTRICT",
            name="fk_runtime_grant_event_binding_scope",
        ),
        sa.ForeignKeyConstraint(
            ["actor_membership_id", "actor_user_id", "organization_id"],
            ["memberships.id", "memberships.user_id", "memberships.organization_id"],
            ondelete="RESTRICT",
            name="fk_runtime_grant_event_actor_scope",
        ),
        sa.ForeignKeyConstraint(
            ["target_role_id", "organization_id"],
            ["roles.id", "roles.organization_id"],
            ondelete="RESTRICT",
            name="fk_runtime_grant_event_role_scope",
        ),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "actor_principal_id = actor_user_id", name="ck_runtime_grant_event_actor_identity"
        ),
        sa.CheckConstraint(
            "operation IN ('grant', 'revoke')", name="ck_runtime_grant_event_operation"
        ),
        sa.CheckConstraint(
            "(operation = 'grant' AND NOT prior_active AND resulting_active) OR (operation = 'revoke' AND prior_active AND NOT resulting_active)",  # noqa: E501
            name="ck_runtime_grant_event_transition",
        ),
        sa.CheckConstraint("grant_revision >= 1", name="ck_runtime_grant_event_revision"),
        sa.CheckConstraint(
            "char_length(reason_reference) BETWEEN 1 AND 200 AND reason_reference = btrim(reason_reference)",  # noqa: E501
            name="ck_runtime_grant_event_reason",
        ),
        sa.CheckConstraint(
            "char_length(provenance_reference) BETWEEN 1 AND 200 AND provenance_reference = btrim(provenance_reference)",  # noqa: E501
            name="ck_runtime_grant_event_provenance",
        ),
        sa.CheckConstraint(
            "char_length(request_digest) BETWEEN 16 AND 200", name="ck_runtime_grant_event_digest"
        ),
        sa.CheckConstraint(
            "classification_ceiling IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_runtime_grant_event_classification",
        ),
        sa.CheckConstraint(
            "committed_at >= requested_at", name="ck_runtime_grant_event_time_order"
        ),
    )
    op.create_index(
        "ix_runtime_grant_event_target",
        "runtime_permission_grant_events",
        ["tenant_id", "organization_id", "target_role_id", "permission_id", "grant_revision"],
    )
    op.create_index(
        "ix_runtime_grant_event_actor",
        "runtime_permission_grant_events",
        ["organization_id", "actor_principal_id", "committed_at"],
    )
    op.execute(
        "CREATE FUNCTION deny_runtime_permission_grant_event_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'runtime permission grant events are append-only'; END; $$"  # noqa: E501
    )
    op.execute(
        "CREATE TRIGGER trg_runtime_permission_grant_events_immutable BEFORE UPDATE OR DELETE ON runtime_permission_grant_events FOR EACH ROW EXECUTE FUNCTION deny_runtime_permission_grant_event_mutation()"  # noqa: E501
    )
    if not rows:
        bind.execute(
            table.insert().values(
                id=_MANAGE[0],
                key=_MANAGE[1],
                name=_MANAGE[2],
                description=_MANAGE[3],
                created_at=_FIXED_TIME,
                updated_at=_FIXED_TIME,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    events = sa.table("runtime_permission_grant_events", sa.column("event_id", sa.Uuid()))
    if int(bind.scalar(sa.select(sa.func.count()).select_from(events)) or 0) or _grant_count(bind):
        raise RuntimeError("Populated Runtime grant governance cannot be downgraded")
    table = _permissions()
    rows = _manage_rows(bind, table)
    if len(rows) != 1 or not _exact(rows[0]):
        raise RuntimeError("Runtime grant management permission mismatch")
    op.execute(
        "DROP TRIGGER trg_runtime_permission_grant_events_immutable ON runtime_permission_grant_events"  # noqa: E501
    )
    op.execute("DROP FUNCTION deny_runtime_permission_grant_event_mutation()")
    op.drop_table("runtime_permission_grant_events")
    op.drop_constraint("uq_roles_id_organization", "roles", type_="unique")
    op.drop_constraint("uq_memberships_actor_scope", "memberships", type_="unique")
    op.drop_constraint(
        "uq_tenant_org_binding_scope", "tenant_organization_bindings", type_="unique"
    )
    bind.execute(table.delete().where(table.c.id == _MANAGE_ID))
