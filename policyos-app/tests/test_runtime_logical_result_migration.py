import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/20260808_0025_runtime_logical_result_classification.py"
MIGRATION_TEST_DATABASE = "policyos_logical_result_migration_test"


def _database_url() -> str:
    value = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for PostgreSQL migration acceptance")
    return value


def _asyncpg_url(value: str) -> str:
    return value.replace("postgresql+asyncpg://", "postgresql://")


def _alembic(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _run_alembic(operation, config: Config, revision: str, url: str) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    try:
        operation(config, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


async def _create_migration_test_database(url: str) -> None:
    connection = await asyncpg.connect(_asyncpg_url(url), database="postgres")
    try:
        await connection.execute(f'CREATE DATABASE "{MIGRATION_TEST_DATABASE}"')
    finally:
        await connection.close()


async def _drop_migration_test_database(url: str) -> None:
    connection = await asyncpg.connect(_asyncpg_url(url), database="postgres")
    try:
        await connection.execute(f'DROP DATABASE "{MIGRATION_TEST_DATABASE}"')
    finally:
        await connection.close()


@pytest.fixture
def migration_database_url() -> str:
    source_url = _database_url()
    isolated_url = (
        make_url(source_url)
        .set(database=MIGRATION_TEST_DATABASE)
        .render_as_string(hide_password=False)
    )
    asyncio.run(_create_migration_test_database(source_url))
    try:
        yield isolated_url
    finally:
        asyncio.run(_drop_migration_test_database(source_url))


def test_migration_declares_closed_backfill_and_trigger_ordering() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert source.index("_preflight()") < source.index("op.add_column(")
    assert "count(request.runtime_repository_write_receipt_id) <> 1" in source
    assert "count(DISTINCT request.classification) <> 1" in source
    assert "result_payload ? 'execution_request_classification'" in source
    assert "jsonb_typeof(result_payload) <> 'object'" in source
    assert "request and attempt identity is duplicated" in source
    assert source.index('f"DROP TRIGGER {_TRIGGER}') < source.index("UPDATE {_REVISIONS}")
    assert source.rindex("_restore_trigger()") > source.index("UPDATE {_REVISIONS}")
    assert "populated logical-result classification cannot be downgraded" in source


def test_model_uses_source_classification_only_for_request_revision_fk() -> None:
    from app.models.runtime_logical_result import (
        RuntimeLogicalExecutionResultRecord,
        RuntimeLogicalExecutionResultRevisionRecord,
    )

    identity_columns = RuntimeLogicalExecutionResultRecord.__table__.columns
    revision = RuntimeLogicalExecutionResultRevisionRecord.__table__
    assert "execution_request_classification" not in identity_columns
    assert revision.c.execution_request_classification.nullable is False
    request_fk = next(
        constraint
        for constraint in revision.foreign_key_constraints
        if constraint.name == "fk_runtime_logical_result_execution_request"
    )
    assert tuple(element.parent.name for element in request_fk.elements) == (
        "execution_request_record_type",
        "tenant_id",
        "organization_id",
        "execution_request_classification",
        "runtime_execution_request_id",
        "execution_request_expected_revision",
    )


def test_postgresql_historical_backfill_and_populated_downgrade_fail_closed(
    migration_database_url: str,
) -> None:
    url = migration_database_url
    config = _alembic(url)
    _run_alembic(command.upgrade, config, "20260808_0024", url)
    tenant = UUID("00000000-0000-0000-0000-000000009001")
    organization = UUID("00000000-0000-0000-0000-000000009002")
    request_id = UUID("00000000-0000-0000-0000-000000009003")
    attempt_id = UUID("00000000-0000-0000-0000-000000009004")
    logical_id = UUID("00000000-0000-0000-0000-000000009005")
    state_id = UUID("00000000-0000-0000-0000-000000009006")
    audit_id = UUID("00000000-0000-0000-0000-000000009007")
    now = datetime(2026, 8, 31, tzinfo=UTC)

    async def seed() -> None:
        connection = await asyncpg.connect(_asyncpg_url(url))
        transaction = connection.transaction()
        await transaction.start()
        for receipt, record_type, record_id, classification in (
            (
                "00000000-0000-0000-0000-000000009011",
                "execution_request",
                request_id,
                "confidential",
            ),
            ("00000000-0000-0000-0000-000000009012", "execution_state", state_id, "confidential"),
            ("00000000-0000-0000-0000-000000009013", "audit_trail", audit_id, "confidential"),
        ):
            await connection.execute(
                """
                    INSERT INTO runtime_record_revisions (
                        runtime_repository_write_receipt_id, runtime_transaction_id,
                        record_type, record_id, tenant_id, organization_id, classification,
                        record_revision, record_digest_reference, payload, requested_at, stored_at
                    ) VALUES (
                        $1, '00000000-0000-0000-0000-000000009099',
                        $2, $3, $4, $5, $6,
                        1, $7, CAST('{}' AS jsonb), $8, $8
                    )
                """,
                UUID(receipt),
                record_type,
                record_id,
                tenant,
                organization,
                classification,
                f"digest:{record_type}",
                now,
            )
        await connection.execute(
            """
                INSERT INTO runtime_logical_execution_results VALUES (
                    $1, $2, $3, 'confidential', $4, $5,
                    '00000000-0000-0000-0000-000000009008', 'lineage:digest'
                )
            """,
            logical_id,
            tenant,
            organization,
            request_id,
            attempt_id,
        )
        await connection.execute(
            """
                INSERT INTO runtime_logical_execution_result_revisions (
                    runtime_logical_execution_result_id, result_revision, tenant_id,
                    organization_id, classification, runtime_execution_request_id,
                    execution_request_expected_revision, attempt_id, root_lineage_id,
                    root_lineage_digest_reference, runtime_execution_state_record_id,
                    execution_state_expected_revision, runtime_audit_trail_id,
                    audit_trail_expected_revision, execution_request_record_type,
                    execution_state_record_type, audit_trail_record_type, result_reference,
                    result_digest_reference, result_payload_provenance_reference,
                    result_payload, produced_at, stored_at
                ) VALUES (
                    $1, 1, $2, $3, 'confidential', $4, 1,
                    $5, '00000000-0000-0000-0000-000000009008', 'lineage:digest',
                    $6, 1, $7, 1, 'execution_request', 'execution_state',
                    'audit_trail', 'result:1', 'result:digest', 'payload:source',
                    CAST('{}' AS jsonb), $8, $8
                )
            """,
            logical_id,
            tenant,
            organization,
            request_id,
            attempt_id,
            state_id,
            audit_id,
            now,
        )
        await transaction.commit()
        await connection.close()

    asyncio.run(seed())
    _run_alembic(command.upgrade, config, "20260808_0025", url)

    async def verify() -> None:
        connection = await asyncpg.connect(_asyncpg_url(url))
        row = await connection.fetchrow(
            "SELECT execution_request_classification, "
            "result_payload ->> 'execution_request_classification' AS payload_value "
            "FROM runtime_logical_execution_result_revisions"
        )
        assert tuple(row) == ("confidential", "confidential")
        trigger_count = await connection.fetchval(
            "SELECT count(*) FROM pg_trigger "
            "WHERE tgname = 'trg_runtime_logical_execution_result_revisions_immutable' "
            "AND NOT tgisinternal"
        )
        assert trigger_count == 1
        await connection.close()

    asyncio.run(verify())
    with pytest.raises(Exception, match="populated logical-result classification"):
        _run_alembic(command.downgrade, config, "20260808_0024", url)

    async def verify_version() -> None:
        connection = await asyncpg.connect(_asyncpg_url(url))
        assert await connection.fetchval("SELECT version_num FROM alembic_version") == (
            "20260808_0025"
        )
        await connection.close()

    asyncio.run(verify_version())
