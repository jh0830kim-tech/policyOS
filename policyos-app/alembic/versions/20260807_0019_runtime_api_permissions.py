"""Persist exact Runtime API permission definitions without granting authority."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_0019"
down_revision: str | None = "20260807_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
_FIXED_TIMESTAMP = datetime(2026, 8, 7, tzinfo=UTC)
_PERMISSION_DEFINITIONS = (
    (
        UUID("00000000-0000-0000-0000-000000001901"),
        "runtime.read",
        "Runtime read",
        "Read governed Runtime invocation status.",
    ),
    (
        UUID("00000000-0000-0000-0000-000000001902"),
        "runtime.invoke",
        "Runtime invoke",
        "Submit governed Runtime invocations.",
    ),
    (
        UUID("00000000-0000-0000-0000-000000001903"),
        "runtime.reconcile",
        "Runtime reconcile",
        "Request governed Runtime reconciliation.",
    ),
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


def _rows(
    bind: sa.Connection, table: sa.Table, permission_id: UUID, key: str
) -> list[sa.RowMapping]:
    return list(
        bind.execute(
            sa.select(table.c.id, table.c.key, table.c.name, table.c.description).where(
                sa.or_(table.c.id == permission_id, table.c.key == key)
            )
        ).mappings()
    )


def _exact(row: sa.RowMapping, permission_id: UUID, key: str, name: str, description: str) -> bool:
    return (row["id"], row["key"], row["name"], row["description"]) == (
        permission_id,
        key,
        name,
        description,
    )


def upgrade() -> None:
    bind = op.get_bind()
    table = _permissions()
    for permission_id, key, name, description in _PERMISSION_DEFINITIONS:
        rows = _rows(bind, table, permission_id, key)
        if not rows:
            bind.execute(
                table.insert().values(
                    id=permission_id,
                    key=key,
                    name=name,
                    description=description,
                    created_at=_FIXED_TIMESTAMP,
                    updated_at=_FIXED_TIMESTAMP,
                )
            )
        elif len(rows) != 1 or not _exact(rows[0], permission_id, key, name, description):
            raise RuntimeError("Runtime permission definition collision")


def downgrade() -> None:
    bind = op.get_bind()
    table = _permissions()
    ids = tuple(item[0] for item in _PERMISSION_DEFINITIONS)
    for permission_id, key, name, description in _PERMISSION_DEFINITIONS:
        rows = _rows(bind, table, permission_id, key)
        if len(rows) != 1 or not _exact(rows[0], permission_id, key, name, description):
            raise RuntimeError("Runtime permission definition mismatch")
    grants = sa.table("role_permissions", sa.column("permission_id", sa.Uuid()))
    if (
        bind.scalar(
            sa.select(sa.func.count()).select_from(grants).where(grants.c.permission_id.in_(ids))
        )
        != 0
    ):
        raise RuntimeError("Runtime permission definitions are still granted")
    bind.execute(table.delete().where(table.c.id.in_(ids)))
