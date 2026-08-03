"""Add append-only governed runtime persistence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260803_0015"
down_revision: str | None = "20260720_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "runtime_record_heads",
        sa.Column("runtime_record_head_id", sa.Uuid(), nullable=False),
        sa.Column("record_type", sa.String(length=40), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("current_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("current_digest_reference", sa.String(length=200), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("runtime_record_head_id"),
        sa.UniqueConstraint(
            "record_type",
            "tenant_id",
            "organization_id",
            "record_id",
            name="uq_runtime_record_head_scope",
        ),
    )
    op.create_index(
        "ix_runtime_record_head_lookup",
        "runtime_record_heads",
        ["record_type", "tenant_id", "organization_id", "record_id"],
    )

    op.create_table(
        "runtime_record_revisions",
        sa.Column("runtime_repository_write_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_repository_write_request_id", sa.Uuid(), nullable=True),
        sa.Column("runtime_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("record_type", sa.String(length=40), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("record_revision", sa.Integer(), nullable=False),
        sa.Column("record_digest_reference", sa.String(length=200), nullable=False),
        sa.Column("payload", JSON_DOCUMENT, nullable=False),
        sa.Column("runtime_execution_request_id", sa.Uuid(), nullable=True),
        sa.Column("execution_plan_step_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("action_definition_id", sa.String(length=200), nullable=True),
        sa.Column("action", sa.String(length=200), nullable=True),
        sa.Column("action_version", sa.String(length=100), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(runtime_repository_write_request_id IS NULL) <> "
            "(runtime_transaction_id IS NULL)",
            name="ck_runtime_revision_exactly_one_write_source",
        ),
        sa.PrimaryKeyConstraint("runtime_repository_write_receipt_id"),
        sa.UniqueConstraint(
            "record_type",
            "tenant_id",
            "organization_id",
            "record_id",
            "record_revision",
            name="uq_runtime_record_revision_scope",
        ),
        sa.UniqueConstraint(
            "runtime_repository_write_request_id",
            name="uq_runtime_record_revision_write_request",
        ),
        sa.UniqueConstraint(
            "record_type",
            "tenant_id",
            "organization_id",
            "runtime_execution_request_id",
            "execution_plan_step_id",
            "attempt_id",
            "action_definition_id",
            "action",
            "action_version",
            "idempotency_key",
            name="uq_runtime_record_idempotency_scope",
        ),
    )
    op.create_index(
        "ix_runtime_record_revision_lookup",
        "runtime_record_revisions",
        [
            "record_type",
            "tenant_id",
            "organization_id",
            "record_id",
            "record_revision",
        ],
    )

    op.create_table(
        "runtime_transaction_records",
        sa.Column("runtime_transaction_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("state_record_revision", sa.Integer(), nullable=False),
        sa.Column("audit_trail_revision", sa.Integer(), nullable=False),
        sa.Column("idempotency_reservation_id", sa.Uuid(), nullable=False),
        sa.Column("outbox_enqueue_record_id", sa.Uuid(), nullable=True),
        sa.Column("persisted_record_receipt_ids", JSON_DOCUMENT, nullable=False),
        sa.Column("transaction_digest_reference", sa.String(length=200), nullable=False),
        sa.Column("clock_reference", sa.String(length=200), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("runtime_transaction_receipt_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_transaction_id",
            name="uq_runtime_transaction_scope",
        ),
    )
    op.create_index(
        "ix_runtime_transaction_scope",
        "runtime_transaction_records",
        ["tenant_id", "organization_id", "runtime_transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_runtime_transaction_scope", table_name="runtime_transaction_records")
    op.drop_table("runtime_transaction_records")
    op.drop_index("ix_runtime_record_revision_lookup", table_name="runtime_record_revisions")
    op.drop_table("runtime_record_revisions")
    op.drop_index("ix_runtime_record_head_lookup", table_name="runtime_record_heads")
    op.drop_table("runtime_record_heads")
