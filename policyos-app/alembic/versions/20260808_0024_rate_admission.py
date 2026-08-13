"""Persist ADR-103 rate admission and ADR-104 permission definition."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260808_0024"
down_revision: str | None = "20260808_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSION_ID = UUID("00000000-0000-0000-0000-000000001905")
_PERMISSION = (
    _PERMISSION_ID,
    "runtime.rate_policy.manage",
    "Runtime rate-policy management",
    "Manage governed Runtime rate-policy revisions and revocations.",
)
_FIXED_TIME = datetime(2026, 8, 13, tzinfo=UTC)
_TABLES = (
    "runtime_rate_policy_revisions",
    "runtime_rate_policy_revocations",
    "runtime_rate_admission_decisions",
    "runtime_rate_window_counters",
)
_POLICY_COLUMNS = (
    "tenant_id",
    "organization_id",
    "principal_id",
    "operation",
    "classification",
    "policy_id",
    "policy_revision",
    "policy_reference",
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


def _permission_rows(bind: sa.Connection, table: sa.Table) -> list[sa.RowMapping]:
    return list(
        bind.execute(
            sa.select(table.c.id, table.c.key, table.c.name, table.c.description).where(
                sa.or_(table.c.id == _PERMISSION_ID, table.c.key == _PERMISSION[1])
            )
        ).mappings()
    )


def _permission_exact(row: sa.RowMapping) -> bool:
    return (row["id"], row["key"], row["name"], row["description"]) == _PERMISSION


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    permissions = _permissions()
    rows = _permission_rows(bind, permissions)
    if rows and (len(rows) != 1 or not _permission_exact(rows[0])):
        raise RuntimeError("Runtime rate-policy management permission collision")

    op.create_table(
        "runtime_rate_policy_revisions",
        sa.Column("tenant_id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), primary_key=True),
        sa.Column("principal_id", sa.Uuid(), primary_key=True),
        sa.Column("operation", sa.String(40), primary_key=True),
        sa.Column("classification", sa.String(20), primary_key=True),
        sa.Column("policy_id", sa.Uuid(), primary_key=True),
        sa.Column("policy_revision", sa.Integer(), primary_key=True),
        sa.Column("policy_reference", sa.String(200), nullable=False),
        sa.Column("admission_limit", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provisioning_request_id", sa.Uuid(), nullable=False),
        sa.Column("provisioning_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("actor_principal_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_membership_id", sa.Uuid(), nullable=False),
        sa.Column("reason_reference", sa.String(200), nullable=False),
        sa.Column("provenance_reference", sa.String(200), nullable=False),
        sa.Column("request_digest", sa.String(200), nullable=False),
        sa.Column("command_version", sa.String(200), nullable=False),
        sa.Column("permission_reference", sa.String(200), nullable=False),
        sa.Column("provision_payload", _json_type(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            *_POLICY_COLUMNS,
            name="uq_runtime_rate_policy_exact_identity",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "provisioning_request_id",
            name="uq_runtime_rate_policy_provision_request",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "provisioning_receipt_id",
            name="uq_runtime_rate_policy_provision_receipt",
        ),
        sa.ForeignKeyConstraint(
            ("tenant_id", "organization_id"),
            (
                "tenant_organization_bindings.runtime_tenant_id",
                "tenant_organization_bindings.organization_id",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_rate_policy_scope",
        ),
        sa.ForeignKeyConstraint(
            ("actor_membership_id", "actor_user_id", "organization_id"),
            ("memberships.id", "memberships.user_id", "memberships.organization_id"),
            ondelete="RESTRICT",
            name="fk_runtime_rate_policy_actor",
        ),
        sa.CheckConstraint(
            "classification IN ('public','internal','confidential','restricted')",
            name="ck_runtime_rate_policy_classification",
        ),
        sa.CheckConstraint(
            "operation IN ('submit_invocation','get_invocation','request_reconciliation')",
            name="ck_runtime_rate_policy_operation",
        ),
        sa.CheckConstraint("policy_revision >= 1", name="ck_runtime_rate_policy_revision"),
        sa.CheckConstraint(
            "admission_limit BETWEEN 1 AND 1000000",
            name="ck_runtime_rate_policy_limit",
        ),
        sa.CheckConstraint(
            "window_seconds BETWEEN 1 AND 86400",
            name="ck_runtime_rate_policy_window",
        ),
        sa.CheckConstraint(
            "effective_from < valid_until",
            name="ck_runtime_rate_policy_validity",
        ),
        sa.CheckConstraint(
            "requested_at <= committed_at",
            name="ck_runtime_rate_policy_commit_order",
        ),
        sa.CheckConstraint(
            "actor_principal_id = actor_user_id",
            name="ck_runtime_rate_policy_actor_identity",
        ),
    )
    op.create_index(
        "ix_runtime_rate_policy_lookup",
        "runtime_rate_policy_revisions",
        list(_POLICY_COLUMNS),
    )

    op.create_table(
        "runtime_rate_policy_revocations",
        sa.Column("tenant_id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), primary_key=True),
        sa.Column("revocation_request_id", sa.Uuid(), primary_key=True),
        sa.Column("revocation_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("policy_reference", sa.String(200), nullable=False),
        sa.Column("actor_principal_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_membership_id", sa.Uuid(), nullable=False),
        sa.Column("reason_reference", sa.String(200), nullable=False),
        sa.Column("provenance_reference", sa.String(200), nullable=False),
        sa.Column("request_digest", sa.String(200), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocation_payload", _json_type(), nullable=False),
        sa.ForeignKeyConstraint(
            _POLICY_COLUMNS,
            tuple(f"runtime_rate_policy_revisions.{value}" for value in _POLICY_COLUMNS),
            ondelete="RESTRICT",
            name="fk_runtime_rate_revocation_policy",
        ),
        sa.ForeignKeyConstraint(
            ("actor_membership_id", "actor_user_id", "organization_id"),
            ("memberships.id", "memberships.user_id", "memberships.organization_id"),
            ondelete="RESTRICT",
            name="fk_runtime_rate_revocation_actor",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "revocation_receipt_id",
            name="uq_runtime_rate_revocation_receipt",
        ),
        sa.UniqueConstraint(
            *_POLICY_COLUMNS,
            name="uq_runtime_rate_revocation_policy",
        ),
        sa.CheckConstraint(
            "classification IN ('public','internal','confidential','restricted')",
            name="ck_runtime_rate_revocation_classification",
        ),
        sa.CheckConstraint(
            "operation IN ('submit_invocation','get_invocation','request_reconciliation')",
            name="ck_runtime_rate_revocation_operation",
        ),
        sa.CheckConstraint(
            "actor_principal_id = actor_user_id",
            name="ck_runtime_rate_revocation_actor_identity",
        ),
    )
    op.create_index(
        "ix_runtime_rate_revocation_lookup",
        "runtime_rate_policy_revocations",
        list(_POLICY_COLUMNS),
    )

    op.create_table(
        "runtime_rate_admission_decisions",
        sa.Column("decision_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("policy_reference", sa.String(200), nullable=False),
        sa.Column("preparation_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_digest", sa.String(200), nullable=False),
        sa.Column("clock_reference", sa.String(200), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disposition", sa.String(20), nullable=False),
        sa.Column("retry_after_seconds", sa.Integer(), nullable=True),
        sa.Column("admitted_count_before", sa.Integer(), nullable=False),
        sa.Column("admitted_count_after", sa.Integer(), nullable=False),
        sa.Column("decision_reference", sa.String(200), nullable=False),
        sa.Column("decision_digest", sa.String(200), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provenance_reference", sa.String(200), nullable=False),
        sa.Column("decision_payload", _json_type(), nullable=False),
        sa.ForeignKeyConstraint(
            _POLICY_COLUMNS,
            tuple(f"runtime_rate_policy_revisions.{value}" for value in _POLICY_COLUMNS),
            ondelete="RESTRICT",
            name="fk_runtime_rate_decision_policy",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "request_id",
            name="uq_runtime_rate_decision_request",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "preparation_id",
            name="uq_runtime_rate_decision_preparation",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "decision_reference",
            name="uq_runtime_rate_decision_reference",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "organization_id",
            "decision_digest",
            name="uq_runtime_rate_decision_digest",
        ),
        sa.CheckConstraint(
            "window_start < window_end AND window_start <= observed_at "
            "AND observed_at < window_end",
            name="ck_runtime_rate_decision_window",
        ),
        sa.CheckConstraint(
            "observed_at = evaluated_at AND evaluated_at <= committed_at",
            name="ck_runtime_rate_decision_time_binding",
        ),
        sa.CheckConstraint(
            "(disposition = 'admitted' AND retry_after_seconds IS NULL "
            "AND admitted_count_after = admitted_count_before + 1) OR "
            "(disposition = 'denied' AND retry_after_seconds BETWEEN 1 AND 86400 "
            "AND admitted_count_after = admitted_count_before)",
            name="ck_runtime_rate_decision_outcome",
        ),
        sa.CheckConstraint(
            "admitted_count_before BETWEEN 0 AND 1000000 "
            "AND admitted_count_after BETWEEN 0 AND 1000000",
            name="ck_runtime_rate_decision_counts",
        ),
    )
    op.create_index(
        "ix_runtime_rate_decision_window",
        "runtime_rate_admission_decisions",
        [*_POLICY_COLUMNS, "window_start", "window_end", "committed_at"],
    )

    op.create_table(
        "runtime_rate_window_counters",
        *(
            sa.Column(name, sa.Uuid() if name.endswith("_id") else sa.String(40), primary_key=True)
            for name in _POLICY_COLUMNS[:4]
        ),
        sa.Column("classification", sa.String(20), primary_key=True),
        sa.Column("policy_id", sa.Uuid(), primary_key=True),
        sa.Column("policy_revision", sa.Integer(), primary_key=True),
        sa.Column("policy_reference", sa.String(200), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("window_end", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("admitted_count", sa.Integer(), nullable=False),
        sa.Column("last_decision_id", sa.Uuid(), nullable=False),
        sa.Column("last_request_id", sa.Uuid(), nullable=False),
        sa.Column("last_preparation_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            _POLICY_COLUMNS,
            tuple(f"runtime_rate_policy_revisions.{value}" for value in _POLICY_COLUMNS),
            ondelete="RESTRICT",
            name="fk_runtime_rate_counter_policy",
        ),
        sa.ForeignKeyConstraint(
            ("last_decision_id",),
            ("runtime_rate_admission_decisions.decision_id",),
            ondelete="RESTRICT",
            name="fk_runtime_rate_counter_decision",
        ),
        sa.CheckConstraint(
            "window_start < window_end",
            name="ck_runtime_rate_counter_window",
        ),
        sa.CheckConstraint(
            "admitted_count BETWEEN 1 AND 1000000",
            name="ck_runtime_rate_counter_count",
        ),
    )
    op.create_index(
        "ix_runtime_rate_counter_lookup",
        "runtime_rate_window_counters",
        [*_POLICY_COLUMNS, "window_start", "window_end"],
    )

    op.execute(
        "CREATE FUNCTION deny_runtime_rate_immutable_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION "
        "'runtime rate-admission record is append-only'; END; $$"
    )
    for table in (
        "runtime_rate_policy_revisions",
        "runtime_rate_policy_revocations",
        "runtime_rate_admission_decisions",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON "
            f"{table} FOR EACH ROW EXECUTE FUNCTION "
            "deny_runtime_rate_immutable_mutation()"
        )
    op.execute(
        """
        CREATE FUNCTION enforce_runtime_rate_counter_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'runtime rate counter deletion is forbidden';
          END IF;
          IF TG_OP = 'INSERT' AND NEW.admitted_count <> 1 THEN
            RAISE EXCEPTION 'runtime rate counter must start at one';
          END IF;
          IF TG_OP = 'UPDATE' THEN
            IF (NEW.tenant_id, NEW.organization_id, NEW.principal_id, NEW.operation,
                NEW.classification, NEW.policy_id, NEW.policy_revision, NEW.policy_reference,
                NEW.window_start, NEW.window_end)
               IS DISTINCT FROM
               (OLD.tenant_id, OLD.organization_id, OLD.principal_id, OLD.operation,
                OLD.classification, OLD.policy_id, OLD.policy_revision, OLD.policy_reference,
                OLD.window_start, OLD.window_end)
               OR NEW.admitted_count <> OLD.admitted_count + 1 THEN
              RAISE EXCEPTION 'runtime rate counter update differs';
            END IF;
          END IF;
          PERFORM 1 FROM runtime_rate_admission_decisions AS d
           WHERE d.decision_id = NEW.last_decision_id
             AND d.request_id = NEW.last_request_id
             AND d.preparation_id = NEW.last_preparation_id
             AND d.tenant_id = NEW.tenant_id
             AND d.organization_id = NEW.organization_id
             AND d.principal_id = NEW.principal_id
             AND d.operation = NEW.operation
             AND d.classification = NEW.classification
             AND d.policy_id = NEW.policy_id
             AND d.policy_revision = NEW.policy_revision
             AND d.policy_reference = NEW.policy_reference
             AND d.window_start = NEW.window_start
             AND d.window_end = NEW.window_end
             AND d.disposition = 'admitted'
             AND d.admitted_count_after = NEW.admitted_count
             AND d.admitted_count_before = NEW.admitted_count - 1;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'runtime rate counter lacks exact admitted decision';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER trg_runtime_rate_window_counters_guard BEFORE INSERT OR "
        "UPDATE OR DELETE ON runtime_rate_window_counters FOR EACH ROW EXECUTE "
        "FUNCTION enforce_runtime_rate_counter_mutation()"
    )

    if not rows:
        bind.execute(
            permissions.insert().values(
                id=_PERMISSION[0],
                key=_PERMISSION[1],
                name=_PERMISSION[2],
                description=_PERMISSION[3],
                created_at=_FIXED_TIME,
                updated_at=_FIXED_TIME,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    permissions = _permissions()
    rows = _permission_rows(bind, permissions)
    if len(rows) != 1 or not _permission_exact(rows[0]):
        raise RuntimeError("Runtime rate-policy management permission mismatch")
    populated = tuple(
        name
        for name in _TABLES
        if int(
            bind.scalar(
                sa.select(sa.func.count()).select_from(
                    sa.table(name, sa.column(next(iter(("tenant_id", "decision_id")))))
                )
            )
            or 0
        )
    )
    role_permissions = sa.table("role_permissions", sa.column("permission_id", sa.Uuid()))
    grant_events = sa.table(
        "runtime_permission_grant_events", sa.column("permission_id", sa.Uuid())
    )
    active_grants = int(
        bind.scalar(
            sa.select(sa.func.count())
            .select_from(role_permissions)
            .where(role_permissions.c.permission_id == _PERMISSION_ID)
        )
        or 0
    )
    ledger_references = int(
        bind.scalar(
            sa.select(sa.func.count())
            .select_from(grant_events)
            .where(grant_events.c.permission_id == _PERMISSION_ID)
        )
        or 0
    )
    if populated or active_grants or ledger_references:
        raise RuntimeError("Populated Runtime rate admission cannot be downgraded")

    op.execute(
        "DROP TRIGGER trg_runtime_rate_window_counters_guard ON runtime_rate_window_counters"
    )
    op.execute("DROP FUNCTION enforce_runtime_rate_counter_mutation()")
    for table in (
        "runtime_rate_admission_decisions",
        "runtime_rate_policy_revocations",
        "runtime_rate_policy_revisions",
    ):
        op.execute(f"DROP TRIGGER trg_{table}_immutable ON {table}")
    op.execute("DROP FUNCTION deny_runtime_rate_immutable_mutation()")
    for table in reversed(_TABLES):
        op.drop_table(table)
    bind.execute(permissions.delete().where(permissions.c.id == _PERMISSION_ID))
