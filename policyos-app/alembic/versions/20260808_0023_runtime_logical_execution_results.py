"""Add append-only CP9 logical execution-result persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260808_0023"
down_revision: str | None = "20260808_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "runtime_logical_execution_results",
    "runtime_logical_execution_result_revisions",
)
_RUNTIME_REVISION_TARGET = (
    "runtime_record_revisions.record_type",
    "runtime_record_revisions.tenant_id",
    "runtime_record_revisions.organization_id",
    "runtime_record_revisions.classification",
    "runtime_record_revisions.record_id",
    "runtime_record_revisions.record_revision",
)


def _json() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_runtime_record_revision_exact_scope",
        "runtime_record_revisions",
        (
            "record_type",
            "tenant_id",
            "organization_id",
            "classification",
            "record_id",
            "record_revision",
        ),
    )
    op.create_table(
        "runtime_logical_execution_results",
        sa.Column("runtime_logical_execution_result_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("runtime_execution_request_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("root_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("root_lineage_digest_reference", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("runtime_logical_execution_result_id"),
        sa.CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_runtime_logical_result_classification",
        ),
        sa.CheckConstraint(
            "tenant_id <> organization_id",
            name="ck_runtime_logical_result_scope_distinct",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "classification",
            "runtime_logical_execution_result_id",
            name="uq_runtime_logical_result_scope",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "classification",
            "runtime_execution_request_id",
            "attempt_id",
            name="uq_runtime_logical_result_request_attempt",
        ),
        sa.UniqueConstraint(
            "runtime_logical_execution_result_id",
            "tenant_id",
            "organization_id",
            "classification",
            "runtime_execution_request_id",
            "attempt_id",
            "root_lineage_id",
            "root_lineage_digest_reference",
            name="uq_runtime_logical_result_exact_identity",
        ),
    )
    op.create_table(
        "runtime_logical_execution_result_revisions",
        sa.Column("runtime_logical_execution_result_id", sa.Uuid(), nullable=False),
        sa.Column("result_revision", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("runtime_execution_request_id", sa.Uuid(), nullable=False),
        sa.Column("execution_request_expected_revision", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("root_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("root_lineage_digest_reference", sa.String(200), nullable=False),
        sa.Column("runtime_execution_state_record_id", sa.Uuid(), nullable=False),
        sa.Column("execution_state_expected_revision", sa.Integer(), nullable=False),
        sa.Column("runtime_audit_trail_id", sa.Uuid(), nullable=False),
        sa.Column("audit_trail_expected_revision", sa.Integer(), nullable=False),
        sa.Column("execution_request_record_type", sa.String(40), nullable=False),
        sa.Column("execution_state_record_type", sa.String(40), nullable=False),
        sa.Column("audit_trail_record_type", sa.String(40), nullable=False),
        sa.Column("result_reference", sa.String(200), nullable=False),
        sa.Column("result_digest_reference", sa.String(200), nullable=False),
        sa.Column("result_payload_provenance_reference", sa.String(200), nullable=False),
        sa.Column("result_payload", _json(), nullable=False),
        sa.Column("produced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "runtime_logical_execution_result_id",
            "result_revision",
        ),
        sa.ForeignKeyConstraint(
            (
                "runtime_logical_execution_result_id",
                "tenant_id",
                "organization_id",
                "classification",
                "runtime_execution_request_id",
                "attempt_id",
                "root_lineage_id",
                "root_lineage_digest_reference",
            ),
            (
                "runtime_logical_execution_results.runtime_logical_execution_result_id",
                "runtime_logical_execution_results.tenant_id",
                "runtime_logical_execution_results.organization_id",
                "runtime_logical_execution_results.classification",
                "runtime_logical_execution_results.runtime_execution_request_id",
                "runtime_logical_execution_results.attempt_id",
                "runtime_logical_execution_results.root_lineage_id",
                "runtime_logical_execution_results.root_lineage_digest_reference",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_logical_result_revision_identity",
        ),
        sa.ForeignKeyConstraint(
            (
                "execution_request_record_type",
                "tenant_id",
                "organization_id",
                "classification",
                "runtime_execution_request_id",
                "execution_request_expected_revision",
            ),
            _RUNTIME_REVISION_TARGET,
            ondelete="RESTRICT",
            name="fk_runtime_logical_result_execution_request",
        ),
        sa.ForeignKeyConstraint(
            (
                "execution_state_record_type",
                "tenant_id",
                "organization_id",
                "classification",
                "runtime_execution_state_record_id",
                "execution_state_expected_revision",
            ),
            _RUNTIME_REVISION_TARGET,
            ondelete="RESTRICT",
            name="fk_runtime_logical_result_execution_state",
        ),
        sa.ForeignKeyConstraint(
            (
                "audit_trail_record_type",
                "tenant_id",
                "organization_id",
                "classification",
                "runtime_audit_trail_id",
                "audit_trail_expected_revision",
            ),
            _RUNTIME_REVISION_TARGET,
            ondelete="RESTRICT",
            name="fk_runtime_logical_result_audit_trail",
        ),
        sa.CheckConstraint(
            "result_revision >= 1",
            name="ck_runtime_logical_result_revision",
        ),
        sa.CheckConstraint(
            "execution_request_expected_revision >= 1 AND "
            "execution_state_expected_revision >= 1 AND "
            "audit_trail_expected_revision >= 1",
            name="ck_runtime_logical_result_expected_revisions",
        ),
        sa.CheckConstraint(
            "execution_request_record_type = 'execution_request' AND "
            "execution_state_record_type = 'execution_state' AND "
            "audit_trail_record_type = 'audit_trail'",
            name="ck_runtime_logical_result_record_types",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "classification",
            "runtime_logical_execution_result_id",
            "result_revision",
            name="uq_runtime_logical_result_revision_scope",
        ),
    )
    for table in _TABLES:
        op.execute(
            f"CREATE FUNCTION deny_{table}_mutation() RETURNS trigger LANGUAGE plpgsql "
            f"AS $$ BEGIN RAISE EXCEPTION '{table} rows are immutable'; END; $$"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION deny_{table}_mutation()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    populated = tuple(
        table
        for table in _TABLES
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None
    )
    if populated:
        raise RuntimeError("populated logical execution-result persistence cannot be downgraded")
    for table in reversed(_TABLES):
        op.execute(f"DROP TRIGGER trg_{table}_immutable ON {table}")
        op.execute(f"DROP FUNCTION deny_{table}_mutation()")
        op.drop_table(table)
    op.drop_constraint(
        "uq_runtime_record_revision_exact_scope",
        "runtime_record_revisions",
        type_="unique",
    )
