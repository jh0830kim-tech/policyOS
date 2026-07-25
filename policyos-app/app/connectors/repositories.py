"""Organization-scoped connector persistence repositories."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connectors import (
    ConnectorConfiguration,
    ConnectorExecutionRecord,
    ConnectorHealthState,
    ConnectorSyncState,
)


class ConnectorConfigurationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, item: ConnectorConfiguration) -> ConnectorConfiguration:
        self.db.add(item)
        await self.db.flush()
        return item

    async def get_by_id(
        self, organization_id: uuid.UUID, configuration_id: uuid.UUID
    ) -> ConnectorConfiguration | None:
        return await self.db.scalar(
            select(ConnectorConfiguration).where(
                ConnectorConfiguration.organization_id == organization_id,
                ConnectorConfiguration.id == configuration_id,
            )
        )

    async def get_by_stable_name(
        self, organization_id: uuid.UUID, stable_name: str
    ) -> ConnectorConfiguration | None:
        return await self.db.scalar(
            select(ConnectorConfiguration).where(
                ConnectorConfiguration.organization_id == organization_id,
                ConnectorConfiguration.stable_name == stable_name,
            )
        )

    async def list_for_organization(
        self, organization_id: uuid.UUID, *, offset: int = 0, limit: int = 100
    ) -> list[ConnectorConfiguration]:
        statement = (
            select(ConnectorConfiguration)
            .where(ConnectorConfiguration.organization_id == organization_id)
            .order_by(ConnectorConfiguration.stable_name, ConnectorConfiguration.id)
            .offset(max(offset, 0))
            .limit(min(max(limit, 1), 500))
        )
        return list((await self.db.scalars(statement)).all())


class ConnectorSyncStateRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(
        self, organization_id: uuid.UUID, configuration_id: uuid.UUID, sync_key: str
    ) -> ConnectorSyncState | None:
        return await self.db.scalar(
            select(ConnectorSyncState).where(
                ConnectorSyncState.organization_id == organization_id,
                ConnectorSyncState.connector_configuration_id == configuration_id,
                ConnectorSyncState.sync_key == sync_key,
            )
        )

    async def start(
        self,
        organization_id: uuid.UUID,
        configuration_id: uuid.UUID,
        sync_key: str,
        correlation_id: str,
    ) -> ConnectorSyncState:
        state = await self.get(organization_id, configuration_id, sync_key)
        if state is None:
            state = ConnectorSyncState(
                organization_id=organization_id,
                connector_configuration_id=configuration_id,
                sync_key=sync_key,
            )
            self.db.add(state)
        if state.status == "running":
            raise ValueError("Connector sync is already running")
        state.status = "running"
        state.last_started_at = datetime.now(UTC)
        state.last_completed_at = None
        state.pending_cursor = None
        state.error_code = None
        state.error_summary = None
        state.correlation_id = correlation_id
        for counter in (
            "records_processed",
            "records_created",
            "records_updated",
            "records_skipped",
            "records_failed",
            "pages_processed",
            "bytes_received",
            "retry_count",
            "partial_failure_count",
        ):
            setattr(state, counter, 0)
        await self.db.flush()
        return state

    async def complete(
        self,
        state: ConnectorSyncState,
        *,
        cursor: str | None,
        partial: bool = False,
    ) -> None:
        if state.status != "running":
            raise ValueError("Only running connector syncs can complete")
        now = datetime.now(UTC)
        if cursor is not None:
            state.pending_cursor = cursor
            state.last_cursor = state.pending_cursor
        state.pending_cursor = None
        state.status = "partial" if partial else "succeeded"
        state.last_completed_at = now
        if not partial:
            state.last_successful_sync_at = now
        await self.db.flush()

    async def fail(self, state: ConnectorSyncState, *, error_code: str, error_summary: str) -> None:
        state.status = "failed"
        state.last_completed_at = datetime.now(UTC)
        state.pending_cursor = None
        state.error_code = error_code[:100]
        state.error_summary = error_summary[:500]
        await self.db.flush()

    async def find_stale_running(
        self, organization_id: uuid.UUID, stale_after_seconds: int
    ) -> list[ConnectorSyncState]:
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        statement = (
            select(ConnectorSyncState)
            .where(
                ConnectorSyncState.organization_id == organization_id,
                ConnectorSyncState.status == "running",
                ConnectorSyncState.last_started_at < cutoff,
            )
            .order_by(ConnectorSyncState.last_started_at, ConnectorSyncState.id)
        )
        return list((await self.db.scalars(statement)).all())


class ConnectorHealthStateRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(
        self, organization_id: uuid.UUID, configuration_id: uuid.UUID
    ) -> ConnectorHealthState | None:
        return await self.db.scalar(
            select(ConnectorHealthState).where(
                ConnectorHealthState.organization_id == organization_id,
                ConnectorHealthState.connector_configuration_id == configuration_id,
            )
        )

    async def upsert(
        self,
        organization_id: uuid.UUID,
        configuration_id: uuid.UUID,
        *,
        status: str,
        latency_ms: int,
        error_code: str | None = None,
    ) -> ConnectorHealthState:
        state = await self.get(organization_id, configuration_id)
        if state is None:
            state = ConnectorHealthState(
                organization_id=organization_id,
                connector_configuration_id=configuration_id,
            )
            self.db.add(state)
        now = datetime.now(UTC)
        state.status = status
        state.last_checked_at = now
        state.latency_ms = max(latency_ms, 0)
        state.last_error_code = error_code
        if status == "healthy":
            state.last_success_at = now
            state.consecutive_failure_count = 0
        else:
            state.last_failure_at = now
            state.consecutive_failure_count += 1
        await self.db.flush()
        return state


class ConnectorAuditRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(self, item: ConnectorExecutionRecord) -> ConnectorExecutionRecord:
        self.db.add(item)
        await self.db.flush()
        return item

    async def list_recent(
        self, organization_id: uuid.UUID, *, offset: int = 0, limit: int = 100
    ) -> list[ConnectorExecutionRecord]:
        statement = (
            select(ConnectorExecutionRecord)
            .where(ConnectorExecutionRecord.organization_id == organization_id)
            .order_by(
                ConnectorExecutionRecord.started_at.desc(),
                ConnectorExecutionRecord.id.desc(),
            )
            .offset(max(offset, 0))
            .limit(min(max(limit, 1), 500))
        )
        return list((await self.db.scalars(statement)).all())
