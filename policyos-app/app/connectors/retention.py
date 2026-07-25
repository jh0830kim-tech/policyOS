"""Dry-run-first connector retention cleanup."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.models.connectors import (
    ConnectorConfiguration,
    ConnectorExecutionRecord,
    ConnectorHealthState,
    ConnectorSyncState,
)
from app.models.security_governance import LegalHold


@dataclass(frozen=True)
class ConnectorRetentionResult:
    audit_eligible: int
    failed_sync_eligible: int
    health_eligible: int
    deleted: int
    dry_run: bool


class ConnectorRetentionService:
    def __init__(self, db) -> None:
        self.db = db

    async def cleanup(
        self,
        organization_id,
        *,
        audit_days,
        failed_sync_days,
        health_days=None,
        dry_run=True,
    ):
        held = select(LegalHold.target_id).where(
            LegalHold.organization_id == organization_id,
            LegalHold.target_type == "connector_configuration",
            LegalHold.active.is_(True),
        )
        active = select(ConnectorConfiguration.id).where(
            ConnectorConfiguration.organization_id == organization_id,
            ConnectorConfiguration.enabled.is_(True),
        )
        audits = list(
            (
                await self.db.scalars(
                    select(ConnectorExecutionRecord.id).where(
                        ConnectorExecutionRecord.organization_id == organization_id,
                        ConnectorExecutionRecord.completed_at
                        < datetime.now(UTC) - timedelta(days=audit_days),
                        ConnectorExecutionRecord.connector_configuration_id.not_in(held),
                    )
                )
            ).all()
        )
        failed = list(
            (
                await self.db.scalars(
                    select(ConnectorSyncState.id).where(
                        ConnectorSyncState.organization_id == organization_id,
                        ConnectorSyncState.status.in_({"failed", "cancelled"}),
                        ConnectorSyncState.updated_at
                        < datetime.now(UTC) - timedelta(days=failed_sync_days),
                        ConnectorSyncState.connector_configuration_id.not_in(held),
                        ConnectorSyncState.connector_configuration_id.not_in(active),
                    )
                )
            ).all()
        )
        health = []
        if health_days is not None:
            health = list(
                (
                    await self.db.scalars(
                        select(ConnectorHealthState.id).where(
                            ConnectorHealthState.organization_id == organization_id,
                            ConnectorHealthState.updated_at
                            < datetime.now(UTC) - timedelta(days=health_days),
                            ConnectorHealthState.connector_configuration_id.not_in(held),
                            ConnectorHealthState.connector_configuration_id.not_in(active),
                        )
                    )
                ).all()
            )

        if not dry_run:
            if audits:
                await self.db.execute(
                    delete(ConnectorExecutionRecord).where(ConnectorExecutionRecord.id.in_(audits))
                )
            if failed:
                await self.db.execute(
                    delete(ConnectorSyncState).where(ConnectorSyncState.id.in_(failed))
                )
            if health:
                await self.db.execute(
                    delete(ConnectorHealthState).where(ConnectorHealthState.id.in_(health))
                )
            await self.db.commit()
        return ConnectorRetentionResult(
            len(audits),
            len(failed),
            len(health),
            len(audits) + len(failed) + len(health),
            dry_run,
        )
