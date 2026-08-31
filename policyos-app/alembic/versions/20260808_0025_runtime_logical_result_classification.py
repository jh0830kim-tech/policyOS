"""Backfill exact execution-request classification for logical results."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0025"
down_revision: str | None = "20260808_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IDENTITIES = "runtime_logical_execution_results"
_REVISIONS = "runtime_logical_execution_result_revisions"
_REQUESTS = "runtime_record_revisions"
_TRIGGER = f"trg_{_REVISIONS}_immutable"
_FUNCTION = f"deny_{_REVISIONS}_mutation"
_CLASS_RANK = (
    "CASE {value} WHEN 'public' THEN 0 WHEN 'internal' THEN 1 "
    "WHEN 'confidential' THEN 2 WHEN 'restricted' THEN 3 ELSE NULL END"
)


def _reject_if_present(sql: str, message: str) -> None:
    if op.get_bind().execute(sa.text(sql)).first() is not None:
        raise RuntimeError(message)


def _exact_request_join() -> str:
    return f"""
        FROM {_REVISIONS} logical
        JOIN {_REQUESTS} request
          ON request.record_type = logical.execution_request_record_type
         AND request.tenant_id = logical.tenant_id
         AND request.organization_id = logical.organization_id
         AND request.record_id = logical.runtime_execution_request_id
         AND request.record_revision = logical.execution_request_expected_revision
    """


def _preflight() -> None:
    _reject_if_present(
        f"""
        SELECT 1
        FROM {_REVISIONS} logical
        LEFT JOIN {_REQUESTS} request
          ON request.record_type = 'execution_request'
         AND request.tenant_id = logical.tenant_id
         AND request.organization_id = logical.organization_id
         AND request.record_id = logical.runtime_execution_request_id
         AND request.record_revision = logical.execution_request_expected_revision
        GROUP BY logical.runtime_logical_execution_result_id, logical.result_revision
        HAVING count(request.runtime_repository_write_receipt_id) <> 1
        LIMIT 1
        """,
        "logical-result request revision is missing or ambiguous",
    )
    join = _exact_request_join()
    _reject_if_present(
        f"SELECT 1 {join} WHERE request.classification NOT IN "
        "('public', 'internal', 'confidential', 'restricted') LIMIT 1",
        "logical-result request classification is invalid",
    )
    _reject_if_present(
        f"""
        SELECT 1
        FROM (
            SELECT logical.runtime_logical_execution_result_id
            {join}
            GROUP BY logical.runtime_logical_execution_result_id
            HAVING count(DISTINCT request.classification) <> 1
        ) inconsistent
        LIMIT 1
        """,
        "logical-result revisions disagree on request classification",
    )
    effective_rank = _CLASS_RANK.format(value="logical.classification")
    request_rank = _CLASS_RANK.format(value="request.classification")
    _reject_if_present(
        f"SELECT 1 {join} WHERE ({effective_rank}) < ({request_rank}) LIMIT 1",
        "logical-result classification is lower than its request classification",
    )
    _reject_if_present(
        f"""
        SELECT 1 FROM {_IDENTITIES}
        GROUP BY tenant_id, organization_id, runtime_execution_request_id, attempt_id
        HAVING count(*) > 1 LIMIT 1
        """,
        "logical-result request and attempt identity is duplicated",
    )
    _reject_if_present(
        f"SELECT 1 FROM {_REVISIONS} WHERE jsonb_typeof(result_payload) <> 'object' LIMIT 1",
        "logical-result payload is not an object",
    )
    _reject_if_present(
        f"SELECT 1 FROM {_REVISIONS} "
        "WHERE result_payload ? 'execution_request_classification' LIMIT 1",
        "logical-result payload already contains execution_request_classification",
    )


def _create_request_fk() -> None:
    op.create_foreign_key(
        "fk_runtime_logical_result_execution_request",
        _REVISIONS,
        _REQUESTS,
        (
            "execution_request_record_type",
            "tenant_id",
            "organization_id",
            "execution_request_classification",
            "runtime_execution_request_id",
            "execution_request_expected_revision",
        ),
        (
            "record_type",
            "tenant_id",
            "organization_id",
            "classification",
            "record_id",
            "record_revision",
        ),
        ondelete="RESTRICT",
    )


def _restore_trigger() -> None:
    op.execute(
        f"CREATE TRIGGER {_TRIGGER} BEFORE UPDATE OR DELETE ON {_REVISIONS} "
        f"FOR EACH ROW EXECUTE FUNCTION {_FUNCTION}()"
    )
    _reject_if_present(
        f"""
        SELECT 1 WHERE NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = '{_TRIGGER}' AND NOT tgisinternal
        )
        """,
        "logical-result immutability trigger was not restored",
    )


def upgrade() -> None:
    _preflight()
    op.add_column(
        _REVISIONS,
        sa.Column("execution_request_classification", sa.String(length=20), nullable=True),
    )
    op.execute(f"DROP TRIGGER {_TRIGGER} ON {_REVISIONS}")
    op.execute(
        f"""
        UPDATE {_REVISIONS} AS logical
        SET execution_request_classification = request.classification,
            result_payload = logical.result_payload || jsonb_build_object(
                'execution_request_classification', request.classification
            )
        FROM {_REQUESTS} AS request
        WHERE request.record_type = logical.execution_request_record_type
          AND request.tenant_id = logical.tenant_id
          AND request.organization_id = logical.organization_id
          AND request.record_id = logical.runtime_execution_request_id
          AND request.record_revision = logical.execution_request_expected_revision
        """
    )
    _reject_if_present(
        f"""
        SELECT 1 {_exact_request_join()}
        WHERE logical.execution_request_classification IS NULL
           OR logical.execution_request_classification <> request.classification
           OR logical.result_payload ->> 'execution_request_classification'
              <> request.classification
        LIMIT 1
        """,
        "logical-result classification backfill verification failed",
    )
    op.alter_column(_REVISIONS, "execution_request_classification", nullable=False)
    op.drop_constraint(
        "fk_runtime_logical_result_execution_request", _REVISIONS, type_="foreignkey"
    )
    _create_request_fk()
    op.drop_constraint("uq_runtime_logical_result_request_attempt", _IDENTITIES, type_="unique")
    op.create_unique_constraint(
        "uq_runtime_logical_result_request_attempt",
        _IDENTITIES,
        ("tenant_id", "organization_id", "runtime_execution_request_id", "attempt_id"),
    )
    op.create_check_constraint(
        "ck_runtime_logical_result_request_classification",
        _REVISIONS,
        "execution_request_classification IN ('public', 'internal', 'confidential', 'restricted')",
    )
    effective_rank = _CLASS_RANK.format(value="classification")
    request_rank = _CLASS_RANK.format(value="execution_request_classification")
    op.create_check_constraint(
        "ck_runtime_logical_result_classification_not_lowered",
        _REVISIONS,
        f"({effective_rank}) >= ({request_rank})",
    )
    _restore_trigger()


def downgrade() -> None:
    populated = (
        op.get_bind()
        .execute(
            sa.text(f"SELECT 1 FROM {_IDENTITIES} UNION ALL SELECT 1 FROM {_REVISIONS} LIMIT 1")
        )
        .first()
    )
    if populated is not None:
        raise RuntimeError("populated logical-result classification cannot be downgraded")
    op.drop_constraint(
        "fk_runtime_logical_result_execution_request", _REVISIONS, type_="foreignkey"
    )
    op.drop_constraint(
        "ck_runtime_logical_result_classification_not_lowered", _REVISIONS, type_="check"
    )
    op.drop_constraint(
        "ck_runtime_logical_result_request_classification", _REVISIONS, type_="check"
    )
    op.drop_constraint("uq_runtime_logical_result_request_attempt", _IDENTITIES, type_="unique")
    op.create_unique_constraint(
        "uq_runtime_logical_result_request_attempt",
        _IDENTITIES,
        (
            "tenant_id",
            "organization_id",
            "classification",
            "runtime_execution_request_id",
            "attempt_id",
        ),
    )
    op.create_foreign_key(
        "fk_runtime_logical_result_execution_request",
        _REVISIONS,
        _REQUESTS,
        (
            "execution_request_record_type",
            "tenant_id",
            "organization_id",
            "classification",
            "runtime_execution_request_id",
            "execution_request_expected_revision",
        ),
        (
            "record_type",
            "tenant_id",
            "organization_id",
            "classification",
            "record_id",
            "record_revision",
        ),
        ondelete="RESTRICT",
    )
    op.drop_column(_REVISIONS, "execution_request_classification")
