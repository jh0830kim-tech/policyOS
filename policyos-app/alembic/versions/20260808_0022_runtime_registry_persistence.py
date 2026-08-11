"""Add append-only Runtime Registry and reconciliation request persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260808_0022"
down_revision: str | None = "20260808_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "runtime_registry_snapshots",
    "runtime_registry_snapshot_entries",
    "runtime_registry_resolution_requests",
    "runtime_registry_resolution_decisions",
    "runtime_registry_admission_bindings",
    "runtime_registry_permit_bindings",
    "runtime_reconciliation_requests",
)


def _json() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "runtime_registry_snapshots",
        sa.Column("runtime_registry_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("registry_revision", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("root_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("root_lineage_digest_reference", sa.String(200), nullable=False),
        sa.Column("snapshot_digest_reference", sa.String(200), nullable=False),
        sa.Column("runtime_registry_version", sa.String(100), nullable=False),
        sa.Column("runtime_registry_contract_version", sa.String(100), nullable=False),
        sa.Column("runtime_registry_schema_version", sa.String(100), nullable=False),
        sa.Column("definition_count", sa.Integer(), nullable=False),
        sa.Column("active_count", sa.Integer(), nullable=False),
        sa.Column("disabled_count", sa.Integer(), nullable=False),
        sa.Column("retired_count", sa.Integer(), nullable=False),
        sa.Column("invalidated_count", sa.Integer(), nullable=False),
        sa.Column("audit_digest_reference", sa.String(200), nullable=False),
        sa.Column("snapshot_payload", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("runtime_registry_snapshot_id", "registry_revision"),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_registry_snapshot_id",
            "registry_revision",
            "snapshot_digest_reference",
            name="uq_runtime_registry_snapshot_exact",
        ),
        sa.CheckConstraint(
            "tenant_id <> organization_id", name="ck_runtime_registry_scope_distinct"
        ),
        sa.CheckConstraint("registry_revision >= 1", name="ck_runtime_registry_revision_positive"),
        sa.CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_runtime_registry_snapshot_classification",
        ),
    )
    op.create_index(
        "ix_runtime_registry_snapshot_lookup",
        "runtime_registry_snapshots",
        (
            "tenant_id",
            "organization_id",
            "runtime_registry_snapshot_id",
            "registry_revision",
            "snapshot_digest_reference",
        ),
    )
    op.create_table(
        "runtime_registry_snapshot_entries",
        sa.Column("runtime_registry_snapshot_entry_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_registry_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("registry_revision", sa.Integer(), nullable=False),
        sa.Column("canonical_position", sa.Integer(), nullable=False),
        sa.Column("action_definition_id", sa.String(200), nullable=False),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("action_version", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("entry_payload", _json(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("runtime_registry_snapshot_entry_id"),
        sa.ForeignKeyConstraint(
            ("runtime_registry_snapshot_id", "registry_revision"),
            (
                "runtime_registry_snapshots.runtime_registry_snapshot_id",
                "runtime_registry_snapshots.registry_revision",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_entry_snapshot",
        ),
        sa.UniqueConstraint(
            "runtime_registry_snapshot_id",
            "registry_revision",
            "canonical_position",
            name="uq_runtime_registry_entry_position",
        ),
        sa.UniqueConstraint(
            "runtime_registry_snapshot_id",
            "registry_revision",
            "runtime_registry_snapshot_entry_id",
            name="uq_runtime_registry_entry_identity",
        ),
    )
    op.create_index(
        "uq_runtime_registry_active_action",
        "runtime_registry_snapshot_entries",
        (
            "runtime_registry_snapshot_id",
            "registry_revision",
            "action_definition_id",
            "action",
            "action_version",
        ),
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "runtime_registry_resolution_requests",
        sa.Column("runtime_action_resolution_request_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_registry_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("registry_revision", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("root_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("root_lineage_digest_reference", sa.String(200), nullable=False),
        sa.Column("request_payload", _json(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("runtime_action_resolution_request_id"),
        sa.ForeignKeyConstraint(
            ("runtime_registry_snapshot_id", "registry_revision"),
            (
                "runtime_registry_snapshots.runtime_registry_snapshot_id",
                "runtime_registry_snapshots.registry_revision",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_resolution_request_snapshot",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_action_resolution_request_id",
            name="uq_runtime_registry_resolution_request_scope",
        ),
        sa.UniqueConstraint(
            "runtime_action_resolution_request_id",
            "runtime_registry_snapshot_id",
            "registry_revision",
            name="uq_runtime_registry_resolution_request_exact",
        ),
    )
    op.create_table(
        "runtime_registry_resolution_decisions",
        sa.Column("runtime_action_resolution_decision_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_action_resolution_request_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_registry_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("registry_revision", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("decision_status", sa.String(30), nullable=False),
        sa.Column("resolved_snapshot_entry_id", sa.Uuid()),
        sa.Column("decision_payload", _json(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("runtime_action_resolution_decision_id"),
        sa.ForeignKeyConstraint(
            (
                "runtime_action_resolution_request_id",
                "runtime_registry_snapshot_id",
                "registry_revision",
            ),
            (
                "runtime_registry_resolution_requests.runtime_action_resolution_request_id",
                "runtime_registry_resolution_requests.runtime_registry_snapshot_id",
                "runtime_registry_resolution_requests.registry_revision",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_resolution_decision_request",
        ),
        sa.ForeignKeyConstraint(
            (
                "runtime_registry_snapshot_id",
                "registry_revision",
                "resolved_snapshot_entry_id",
            ),
            (
                "runtime_registry_snapshot_entries.runtime_registry_snapshot_id",
                "runtime_registry_snapshot_entries.registry_revision",
                "runtime_registry_snapshot_entries.runtime_registry_snapshot_entry_id",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_resolution_decision_entry",
        ),
        sa.CheckConstraint(
            "(decision_status = 'resolved' AND resolved_snapshot_entry_id IS NOT NULL) OR "
            "(decision_status <> 'resolved' AND resolved_snapshot_entry_id IS NULL)",
            name="ck_runtime_registry_resolution_decision_entry",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_action_resolution_decision_id",
            name="uq_runtime_registry_resolution_decision_scope",
        ),
        sa.UniqueConstraint(
            "runtime_action_resolution_decision_id",
            "runtime_action_resolution_request_id",
            "runtime_registry_snapshot_id",
            "registry_revision",
            name="uq_runtime_registry_resolution_decision_exact",
        ),
    )
    op.create_table(
        "runtime_registry_admission_bindings",
        sa.Column("runtime_admission_decision_id", sa.Uuid(), nullable=False),
        sa.Column("admission_expected_revision", sa.Integer(), nullable=False),
        sa.Column("runtime_execution_request_id", sa.Uuid(), nullable=False),
        sa.Column("execution_request_expected_revision", sa.Integer(), nullable=False),
        sa.Column("runtime_action_resolution_request_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_action_resolution_decision_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_registry_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("registry_revision", sa.Integer(), nullable=False),
        sa.Column("snapshot_digest_reference", sa.String(200), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("root_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("root_lineage_digest_reference", sa.String(200), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("runtime_admission_decision_id"),
        sa.ForeignKeyConstraint(
            (
                "runtime_action_resolution_decision_id",
                "runtime_action_resolution_request_id",
                "runtime_registry_snapshot_id",
                "registry_revision",
            ),
            (
                "runtime_registry_resolution_decisions.runtime_action_resolution_decision_id",
                "runtime_registry_resolution_decisions.runtime_action_resolution_request_id",
                "runtime_registry_resolution_decisions.runtime_registry_snapshot_id",
                "runtime_registry_resolution_decisions.registry_revision",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_admission_resolution",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_admission_decision_id",
            "admission_expected_revision",
            name="uq_runtime_registry_admission_exact",
        ),
    )
    op.create_table(
        "runtime_registry_permit_bindings",
        sa.Column("runtime_admission_decision_id", sa.Uuid(), nullable=False),
        sa.Column("permit_id", sa.Uuid(), nullable=False),
        sa.Column("expected_revision", sa.Integer(), nullable=False),
        sa.Column("canonical_position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("runtime_admission_decision_id", "permit_id"),
        sa.ForeignKeyConstraint(
            ("runtime_admission_decision_id",),
            ("runtime_registry_admission_bindings.runtime_admission_decision_id",),
            ondelete="RESTRICT",
            name="fk_runtime_registry_permit_admission",
        ),
        sa.UniqueConstraint(
            "runtime_admission_decision_id",
            "canonical_position",
            name="uq_runtime_registry_permit_position",
        ),
        sa.UniqueConstraint(
            "runtime_admission_decision_id",
            "permit_id",
            name="uq_runtime_registry_permit_identity",
        ),
    )
    op.create_table(
        "runtime_reconciliation_requests",
        sa.Column("runtime_effect_reconciliation_request_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_effect_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("runtime_admission_decision_id", sa.Uuid(), nullable=False),
        sa.Column("admission_expected_revision", sa.Integer(), nullable=False),
        sa.Column("runtime_execution_request_id", sa.Uuid(), nullable=False),
        sa.Column("execution_request_expected_revision", sa.Integer(), nullable=False),
        sa.Column("runtime_action_resolution_request_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_action_resolution_decision_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_registry_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("registry_revision", sa.Integer(), nullable=False),
        sa.Column("snapshot_digest_reference", sa.String(200), nullable=False),
        sa.Column("root_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("root_lineage_digest_reference", sa.String(200), nullable=False),
        sa.Column("local_write_set_id", sa.Uuid(), nullable=False),
        sa.Column("transport_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("write_set_digest_reference", sa.String(200), nullable=False),
        sa.Column("request_payload", _json(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("staged_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("runtime_effect_reconciliation_request_id"),
        sa.ForeignKeyConstraint(
            ("runtime_admission_decision_id",),
            ("runtime_registry_admission_bindings.runtime_admission_decision_id",),
            ondelete="RESTRICT",
            name="fk_runtime_reconciliation_request_binding",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_effect_reconciliation_request_id",
            name="uq_runtime_reconciliation_request_scope",
        ),
        sa.UniqueConstraint("local_write_set_id", name="uq_runtime_reconciliation_local_write_set"),
        sa.UniqueConstraint(
            "transport_receipt_id", name="uq_runtime_reconciliation_transport_receipt"
        ),
    )
    for table in _TABLES:
        function = f"deny_{table}_mutation"
        trigger = f"trg_{table}_immutable"
        op.execute(
            f"CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ "
            f"BEGIN RAISE EXCEPTION '{table} rows are immutable'; END; $$"
        )
        op.execute(
            f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        populated = bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first()
        if populated is not None:
            raise RuntimeError("populated Runtime Registry persistence cannot be downgraded")
    for table in reversed(_TABLES):
        op.execute(f"DROP TRIGGER trg_{table}_immutable ON {table}")
        op.execute(f"DROP FUNCTION deny_{table}_mutation()")
        op.drop_table(table)
