"""Persist governed connector configuration, state, health, and execution audit."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0014"
down_revision: str | None = "20260720_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONNECTOR_PERMISSIONS = {
    "connector.read": "00000000-0000-0000-0000-000000001014",
    "connector.manage": "00000000-0000-0000-0000-000000001015",
    "connector.sync": "00000000-0000-0000-0000-000000001016",
    "connector.audit.read": "00000000-0000-0000-0000-000000001017",
}
ADMIN_ROLE_ID = "00000000-0000-0000-0000-000000000101"

TIMESTAMPS = (
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
)


def upgrade() -> None:
    op.create_table(
        "connector_configurations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("stable_name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("connector_type", sa.String(50), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("read_only", sa.Boolean(), nullable=False),
        sa.Column("endpoint_reference", sa.String(2000), nullable=False),
        sa.Column("credential_reference", sa.String(500)),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("max_response_bytes", sa.Integer(), nullable=False),
        sa.Column("supported_operations", sa.JSON(), nullable=False),
        sa.Column("allowed_classifications", sa.JSON(), nullable=False),
        sa.Column("cache_enabled", sa.Boolean(), nullable=False),
        sa.Column("cache_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("allow_stale_cache", sa.Boolean(), nullable=False),
        sa.Column("health_check_enabled", sa.Boolean(), nullable=False),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        *TIMESTAMPS,
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "stable_name", name="uq_connector_config_org_name"),
    )
    op.create_index(
        "ix_connector_config_org_enabled",
        "connector_configurations",
        ["organization_id", "enabled"],
    )
    op.create_index(
        "ix_connector_configurations_organization_id",
        "connector_configurations",
        ["organization_id"],
    )

    op.create_table(
        "connector_sync_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connector_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("sync_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True)),
        sa.Column("last_completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_cursor", sa.String(2000)),
        sa.Column("pending_cursor", sa.String(2000)),
        sa.Column("last_external_version", sa.String(500)),
        sa.Column("last_etag", sa.String(500)),
        sa.Column("last_modified", sa.String(500)),
        *(
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
                "records_processed",
                "records_created",
                "records_updated",
                "records_skipped",
                "records_failed",
                "pages_processed",
                "bytes_received",
                "retry_count",
                "partial_failure_count",
            )
        ),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_summary", sa.String(500)),
        sa.Column("correlation_id", sa.String(200)),
        *TIMESTAMPS,
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connector_configuration_id"], ["connector_configurations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connector_configuration_id", "sync_key", name="uq_connector_sync_config_key"
        ),
    )
    op.create_index(
        "ix_connector_sync_org_status_time",
        "connector_sync_states",
        ["organization_id", "status", "updated_at"],
    )

    op.create_table(
        "connector_health_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("connector_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failure_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("schema_version", sa.String(100)),
        sa.Column("capabilities_hash", sa.String(64)),
        sa.Column("remote_version", sa.String(100)),
        sa.Column("credential_ready", sa.Boolean(), nullable=False),
        sa.Column("configuration_valid", sa.Boolean(), nullable=False),
        sa.Column("endpoint_allowed", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *TIMESTAMPS,
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connector_configuration_id"], ["connector_configurations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connector_configuration_id", name="uq_connector_health_configuration"),
    )
    op.create_index(
        "ix_connector_health_org_status",
        "connector_health_states",
        ["organization_id", "status"],
    )

    op.create_table(
        "connector_execution_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("connector_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("sync_state_id", sa.Uuid()),
        sa.Column("connector_name", sa.String(100), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        *(
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
                "latency_ms",
                "page_count",
                "result_count",
                "bytes_received",
                "retry_count",
            )
        ),
        sa.Column("cache_status", sa.String(30), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("policy_decision", sa.String(50), nullable=False),
        sa.Column("external_transmission", sa.Boolean(), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["connector_configuration_id"], ["connector_configurations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sync_state_id"], ["connector_sync_states.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_connector_execution_org_name_time",
        "connector_execution_records",
        ["organization_id", "connector_name", "started_at"],
    )
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "id": permission_id,
                "key": key,
                "name": key,
                "description": f"Built-in connector permission: {key}",
            }
            for key, permission_id in CONNECTOR_PERMISSIONS.items()
        ],
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    op.bulk_insert(
        role_permissions,
        [
            {"role_id": ADMIN_ROLE_ID, "permission_id": permission_id}
            for permission_id in CONNECTOR_PERMISSIONS.values()
        ],
    )


def downgrade() -> None:
    permission_ids = "', '".join(CONNECTOR_PERMISSIONS.values())
    op.execute(f"DELETE FROM role_permissions WHERE permission_id IN ('{permission_ids}')")
    permission_keys = "', '".join(CONNECTOR_PERMISSIONS)
    op.execute(f"DELETE FROM permissions WHERE key IN ('{permission_keys}')")
    op.drop_table("connector_execution_records")
    op.drop_table("connector_health_states")
    op.drop_table("connector_sync_states")
    op.drop_table("connector_configurations")
