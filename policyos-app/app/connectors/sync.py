"""Incremental sync state management for connectors."""

from __future__ import annotations

from datetime import UTC, datetime

from app.connectors.domain import ConnectorSyncState


class ConnectorSyncService:
    async def mark_success(
        self,
        state: ConnectorSyncState,
        *,
        cursor: str | None = None,
        records_processed: int = 0,
        records_created: int = 0,
        records_updated: int = 0,
        records_skipped: int = 0,
    ) -> ConnectorSyncState:
        state.last_successful_sync_at = datetime.now(UTC)
        state.last_cursor = cursor
        state.records_processed = records_processed
        state.records_created = records_created
        state.records_updated = records_updated
        state.records_skipped = records_skipped
        state.sync_status = "succeeded"
        state.error_code = None
        return state

    async def mark_failure(
        self, state: ConnectorSyncState, *, error_code: str | None = None
    ) -> ConnectorSyncState:
        state.sync_status = "failed"
        state.error_code = error_code
        return state
