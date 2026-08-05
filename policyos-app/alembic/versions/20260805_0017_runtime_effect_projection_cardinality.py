"""Correct repeated lifecycle projection index cardinality."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_0017"
down_revision: str | None = "20260805_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVISIONS = "runtime_effect_lifecycle_revisions"
_SCOPE = ("tenant_id", "organization_id", "runtime_effect_id")
_INDEXES = (
    (
        "uq_runtime_effect_revision_claim",
        "ix_runtime_effect_revision_claim",
        "runtime_effect_claim_id",
        (*_SCOPE, "runtime_effect_claim_id"),
    ),
    (
        "uq_runtime_effect_revision_lease",
        "ix_runtime_effect_revision_lease",
        "lease_id",
        ("tenant_id", "organization_id", "lease_id"),
    ),
    (
        "uq_runtime_effect_revision_attempt",
        "ix_runtime_effect_revision_attempt",
        "runtime_effect_delivery_attempt_id",
        (*_SCOPE, "runtime_effect_delivery_attempt_id"),
    ),
    (
        "uq_runtime_effect_revision_result",
        "ix_runtime_effect_revision_result",
        "runtime_effect_delivery_result_id",
        (*_SCOPE, "runtime_effect_delivery_result_id"),
    ),
)

def _predicate(column: str) -> sa.TextClause:
    return sa.text(f"{column} IS NOT NULL")


def upgrade() -> None:
    for old_name, _, _, _ in _INDEXES:
        op.drop_index(old_name, table_name=_REVISIONS)
    for _, new_name, column, _ in _INDEXES:
        op.create_index(
            new_name,
            _REVISIONS,
            (*_SCOPE, column),
            unique=False,
            postgresql_where=_predicate(column),
        )


def _repeated_projection_exists(column: str, original_columns: tuple[str, ...]) -> bool:
    columns = ", ".join(original_columns)
    statement = sa.text(
        f"SELECT 1 FROM {_REVISIONS} "
        f"WHERE {column} IS NOT NULL "
        f"GROUP BY {columns} HAVING count(*) > 1 LIMIT 1"
    )
    return op.get_bind().execute(statement).first() is not None


def downgrade() -> None:
    repeated = tuple(
        old_name
        for old_name, _, column, original_columns in _INDEXES
        if _repeated_projection_exists(column, original_columns)
    )
    if repeated:
        names = ", ".join(repeated)
        raise RuntimeError(
            "cannot restore CP8 lifecycle projection uniqueness; "
            f"repeated lineage exists for: {names}"
        )

    for _, new_name, _, _ in _INDEXES:
        op.drop_index(new_name, table_name=_REVISIONS)
    for old_name, _, column, original_columns in _INDEXES:
        op.create_index(
            old_name,
            _REVISIONS,
            original_columns,
            unique=True,
            postgresql_where=_predicate(column),
        )
