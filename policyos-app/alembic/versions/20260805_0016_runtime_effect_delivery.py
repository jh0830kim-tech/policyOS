"""Add self-contained CP8 PostgreSQL effect delivery persistence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

revision: str = "20260805_0016"
down_revision: str | None = "20260803_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EFFECTS = "runtime_effects"
_HEADS = "runtime_effect_lifecycle_heads"
_REVISIONS = "runtime_effect_lifecycle_revisions"
_OBSERVATIONS = "runtime_effect_reconciliation_observations"
_TABLE_PRIMARY_KEYS = (
    (_EFFECTS, "runtime_effect_receipt_id"),
    (_HEADS, "tenant_id"),
    (_REVISIONS, "runtime_effect_lifecycle_receipt_id"),
    (_OBSERVATIONS, "runtime_effect_reconciliation_observation_id"),
)
_SCOPE_COLUMNS = ("tenant_id", "organization_id", "runtime_effect_id", "classification")
_SCOPE_TARGETS = (
    "runtime_effects.tenant_id",
    "runtime_effects.organization_id",
    "runtime_effects.runtime_effect_id",
    "runtime_effects.classification",
)


def _uuid(name: str, *, nullable: bool = False, primary_key: bool = False) -> sa.Column:
    return sa.Column(name, sa.Uuid(), nullable=nullable, primary_key=primary_key)


def _json(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.JSONB(), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        _EFFECTS,
        _uuid("runtime_effect_receipt_id", primary_key=True),
        _uuid("runtime_effect_id"),
        _uuid("tenant_id"),
        _uuid("organization_id"),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("effect_idempotency_key", sa.String(200), nullable=False),
        sa.Column("effect_fingerprint_digest_reference", sa.String(200), nullable=False),
        _uuid("runtime_effect_delivery_envelope_id"),
        sa.Column("envelope_digest_reference", sa.String(200), nullable=False),
        _uuid("originating_outbox_enqueue_record_id"),
        _uuid("originating_transaction_id"),
        _uuid("originating_transaction_receipt_id"),
        _json("initial_effect_enqueue_payload"),
        _json("effect_receipt_fact_payload"),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_effect_id",
            name="uq_runtime_effect_scope_id",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "effect_idempotency_key",
            name="uq_runtime_effect_scope_key",
        ),
        sa.UniqueConstraint(*_SCOPE_COLUMNS, name="uq_runtime_effect_scope_classification"),
    )
    op.create_table(
        _HEADS,
        _uuid("tenant_id", primary_key=True),
        _uuid("organization_id", primary_key=True),
        _uuid("runtime_effect_id", primary_key=True),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("current_lifecycle_revision", sa.Integer(), nullable=False),
        _uuid("current_lifecycle_record_id"),
        sa.Column("current_status", sa.String(30), nullable=False),
        sa.Column("current_lifecycle_digest_reference", sa.String(200), nullable=False),
        _json("current_lifecycle_payload"),
        _uuid("active_claim_id", nullable=True),
        _uuid("active_lease_id", nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        _json("active_claim_payload", nullable=True),
        _json("current_retry_decision_payload", nullable=True),
        sa.Column("next_eligible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_attempt_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            _SCOPE_COLUMNS, _SCOPE_TARGETS, name="fk_runtime_effect_head_scope"
        ),
        sa.CheckConstraint(
            "current_lifecycle_revision >= 1", name="ck_runtime_effect_head_revision"
        ),
        sa.CheckConstraint(
            "latest_attempt_count >= 0", name="ck_runtime_effect_head_attempt_count"
        ),
        sa.CheckConstraint(
            "(active_claim_id IS NULL AND active_lease_id IS NULL AND "
            "claim_expires_at IS NULL AND active_claim_payload IS NULL) OR "
            "(active_claim_id IS NOT NULL AND active_lease_id IS NOT NULL AND "
            "claim_expires_at IS NOT NULL AND active_claim_payload IS NOT NULL)",
            name="ck_runtime_effect_head_claim_projection",
        ),
    )
    op.create_index(
        "ix_runtime_effect_due",
        _HEADS,
        ("tenant_id", "organization_id", "classification", "next_eligible_at", "runtime_effect_id"),
        postgresql_where=sa.text("current_status IN ('enqueued', 'retry_scheduled', 'claimed')"),
    )
    op.create_table(
        _REVISIONS,
        _uuid("runtime_effect_lifecycle_receipt_id", primary_key=True),
        _uuid("tenant_id"),
        _uuid("organization_id"),
        sa.Column("classification", sa.String(20), nullable=False),
        _uuid("runtime_effect_id"),
        _uuid("runtime_effect_lifecycle_record_id"),
        sa.Column("lifecycle_revision", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(30), nullable=False),
        sa.Column("lifecycle_digest_reference", sa.String(200), nullable=False),
        _uuid("source_transaction_id", nullable=True),
        _uuid("lifecycle_append_request_id", nullable=True),
        _uuid("claim_request_id", nullable=True),
        _uuid("runtime_effect_claim_id", nullable=True),
        _uuid("lease_id", nullable=True),
        _uuid("runtime_effect_delivery_attempt_id", nullable=True),
        _uuid("runtime_effect_delivery_result_id", nullable=True),
        _uuid("runtime_effect_retry_decision_id", nullable=True),
        _uuid("runtime_effect_dead_letter_record_id", nullable=True),
        _uuid("runtime_effect_definitely_not_invoked_id", nullable=True),
        _uuid("runtime_effect_reconciliation_observation_id", nullable=True),
        _json("lifecycle_record_payload"),
        _json("write_request_payload"),
        _json("claim_payload", nullable=True),
        _json("attempt_payload", nullable=True),
        _json("result_payload", nullable=True),
        _json("definitely_not_invoked_payload", nullable=True),
        _json("retry_decision_payload", nullable=True),
        _json("dead_letter_payload", nullable=True),
        _json("receipt_fact_payload"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            _SCOPE_COLUMNS, _SCOPE_TARGETS, name="fk_runtime_effect_revision_scope"
        ),
        sa.CheckConstraint("lifecycle_revision >= 1", name="ck_runtime_effect_revision_positive"),
        sa.CheckConstraint(
            "num_nonnulls(source_transaction_id, lifecycle_append_request_id, "
            "claim_request_id) = 1",
            name="ck_runtime_effect_revision_one_source",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_effect_id",
            "lifecycle_revision",
            name="uq_runtime_effect_lifecycle_revision",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_effect_lifecycle_record_id",
            name="uq_runtime_effect_lifecycle_record",
        ),
    )
    indexes = (
        (
            "uq_runtime_effect_append_request",
            ("tenant_id", "organization_id", "lifecycle_append_request_id"),
            "lifecycle_append_request_id IS NOT NULL",
        ),
        (
            "uq_runtime_effect_claim_request",
            ("tenant_id", "organization_id", "claim_request_id"),
            "claim_request_id IS NOT NULL",
        ),
        (
            "uq_runtime_effect_revision_lease",
            ("tenant_id", "organization_id", "lease_id"),
            "lease_id IS NOT NULL",
        ),
        (
            "uq_runtime_effect_revision_claim",
            ("tenant_id", "organization_id", "runtime_effect_id", "runtime_effect_claim_id"),
            "runtime_effect_claim_id IS NOT NULL",
        ),
        (
            "uq_runtime_effect_revision_attempt",
            (
                "tenant_id",
                "organization_id",
                "runtime_effect_id",
                "runtime_effect_delivery_attempt_id",
            ),
            "runtime_effect_delivery_attempt_id IS NOT NULL",
        ),
        (
            "uq_runtime_effect_revision_result",
            (
                "tenant_id",
                "organization_id",
                "runtime_effect_id",
                "runtime_effect_delivery_result_id",
            ),
            "runtime_effect_delivery_result_id IS NOT NULL",
        ),
        (
            "uq_runtime_effect_revision_retry",
            (
                "tenant_id",
                "organization_id",
                "runtime_effect_id",
                "runtime_effect_retry_decision_id",
            ),
            "runtime_effect_retry_decision_id IS NOT NULL",
        ),
        (
            "uq_runtime_effect_revision_dead_letter",
            (
                "tenant_id",
                "organization_id",
                "runtime_effect_id",
                "runtime_effect_dead_letter_record_id",
            ),
            "runtime_effect_dead_letter_record_id IS NOT NULL",
        ),
        (
            "uq_runtime_effect_revision_not_invoked",
            (
                "tenant_id",
                "organization_id",
                "runtime_effect_id",
                "runtime_effect_definitely_not_invoked_id",
            ),
            "runtime_effect_definitely_not_invoked_id IS NOT NULL",
        ),
        (
            "uq_runtime_effect_revision_observation",
            (
                "tenant_id",
                "organization_id",
                "runtime_effect_id",
                "runtime_effect_reconciliation_observation_id",
            ),
            "runtime_effect_reconciliation_observation_id IS NOT NULL",
        ),
    )
    for name, columns, predicate in indexes:
        op.create_index(
            name,
            _REVISIONS,
            columns,
            unique=True,
            postgresql_where=sa.text(predicate),
        )
    op.create_table(
        _OBSERVATIONS,
        _uuid("runtime_effect_reconciliation_observation_id", primary_key=True),
        _uuid("runtime_effect_reconciliation_request_id"),
        _uuid("runtime_effect_id"),
        _uuid("tenant_id"),
        _uuid("organization_id"),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("destination_reference", sa.String(200), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        _json("observation_payload"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            _SCOPE_COLUMNS, _SCOPE_TARGETS, name="fk_runtime_effect_observation_scope"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_effect_reconciliation_observation_id",
            name="uq_runtime_effect_observation_scope",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_effect_reconciliation_request_id",
            name="uq_runtime_effect_observation_request",
        ),
    )


def _export_attested() -> bool:
    return context.get_x_argument(as_dictionary=True).get("policyos_cp8_export_attested") == "true"


def downgrade() -> None:
    if context.is_offline_mode() and not _export_attested():
        raise RuntimeError("offline CP8 downgrade requires policyos_cp8_export_attested=true")
    bind = op.get_bind()
    if not context.is_offline_mode() and not _export_attested():
        populated = any(
            bind.execute(
                sa.select(sa.column(primary_key)).select_from(sa.table(table_name)).limit(1)
            ).first()
            is not None
            for table_name, primary_key in _TABLE_PRIMARY_KEYS
        )
        if populated:
            raise RuntimeError("populated CP8 downgrade requires policyos_cp8_export_attested=true")
    for table_name in (_OBSERVATIONS, _REVISIONS, _HEADS, _EFFECTS):
        op.drop_table(table_name)
