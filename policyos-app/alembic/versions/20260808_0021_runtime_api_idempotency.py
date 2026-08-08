"""Add immutable Runtime API transport idempotency receipts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0021"
down_revision: str | None = "20260808_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_api_idempotency_receipts",
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("command_version", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("command_digest", sa.String(200), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("command_correlation_reference", sa.String(200), nullable=False),
        sa.Column("result_reference", sa.String(200), nullable=False),
        sa.Column("invocation_reference", sa.String(200), nullable=False),
        sa.Column("public_status", sa.String(40), nullable=False),
        sa.Column("status_reference", sa.String(200), nullable=False),
        sa.Column("result_correlation_reference", sa.String(200), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("receipt_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "principal_id",
            "operation",
            "command_version",
            "idempotency_key",
            name="uq_runtime_api_idempotency_scope",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "organization_id"],
            [
                "tenant_organization_bindings.runtime_tenant_id",
                "tenant_organization_bindings.organization_id",
            ],
            ondelete="RESTRICT",
            name="fk_runtime_api_idempotency_binding_scope",
        ),
        sa.ForeignKeyConstraint(["principal_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "operation IN ('submit_invocation', 'request_reconciliation')",
            name="ck_runtime_api_idempotency_operation",
        ),
        sa.CheckConstraint(
            "char_length(command_version) BETWEEN 1 AND 40",
            name="ck_runtime_api_idempotency_command_version",
        ),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 100", name="ck_runtime_api_idempotency_key"
        ),
        sa.CheckConstraint(
            "char_length(command_digest) BETWEEN 16 AND 200",
            name="ck_runtime_api_idempotency_digest",
        ),
        sa.CheckConstraint(
            "char_length(command_correlation_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_command_correlation",
        ),
        sa.CheckConstraint(
            "char_length(result_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_result_reference",
        ),
        sa.CheckConstraint(
            "char_length(invocation_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_invocation_reference",
        ),
        sa.CheckConstraint(
            "char_length(status_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_status_reference",
        ),
        sa.CheckConstraint(
            "char_length(result_correlation_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_result_correlation",
        ),
        sa.CheckConstraint(
            "public_status IN ('accepted', 'in_progress', 'succeeded', 'failed', 'ambiguous', 'reconciliation_required', 'dead_lettered')",
            name="ck_runtime_api_idempotency_public_status",
        ),
    )
    op.execute(
        "CREATE FUNCTION deny_runtime_api_idempotency_receipt_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'runtime API idempotency receipts are immutable'; END; $$"
    )
    op.execute(
        "CREATE TRIGGER trg_runtime_api_idempotency_receipts_immutable BEFORE UPDATE OR DELETE ON runtime_api_idempotency_receipts FOR EACH ROW EXECUTE FUNCTION deny_runtime_api_idempotency_receipt_mutation()"
    )


def downgrade() -> None:
    bind = op.get_bind()
    receipts = sa.table("runtime_api_idempotency_receipts", sa.column("receipt_id", sa.Uuid()))
    if int(bind.scalar(sa.select(sa.func.count()).select_from(receipts)) or 0):
        raise RuntimeError("Populated Runtime API idempotency receipts cannot be downgraded")
    op.execute(
        "DROP TRIGGER trg_runtime_api_idempotency_receipts_immutable ON runtime_api_idempotency_receipts"
    )
    op.execute("DROP FUNCTION deny_runtime_api_idempotency_receipt_mutation()")
    op.drop_table("runtime_api_idempotency_receipts")
