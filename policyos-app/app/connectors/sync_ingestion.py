"""Atomic FakeConnector record ingestion and cursor orchestration."""

from datetime import UTC, datetime

from app.connectors.normalization import normalize_external_record
from app.connectors.persistence_ingestion import DatabaseConnectorIngestionService
from app.connectors.repositories import (
    ConnectorAuditRepository,
    ConnectorConfigurationRepository,
    ConnectorSyncStateRepository,
)
from app.models.connectors import ConnectorExecutionRecord


class ConnectorSyncIngestionService:
    def __init__(self, db) -> None:
        self.db = db
        self.configurations = ConnectorConfigurationRepository(db)
        self.states = ConnectorSyncStateRepository(db)
        self.audits = ConnectorAuditRepository(db)
        self.ingestion = DatabaseConnectorIngestionService(db)

    async def run(self, connector_name, records, *, context, sync_key="default", final_cursor=None):
        configuration = await self.configurations.get_by_stable_name(
            context.organization_id, connector_name
        )
        if configuration is None or not configuration.enabled or not configuration.sync_enabled:
            raise ValueError("Connector sync is unavailable")
        state = await self.states.start(
            context.organization_id, configuration.id, sync_key, context.correlation_id
        )
        await self.db.commit()
        started_at = datetime.now(UTC)
        try:
            for payload in records:
                record = normalize_external_record(payload, context=context)
                result = await self.ingestion.ingest(record, context=context)
                state.records_processed += 1
                if result.status == "duplicate":
                    state.records_skipped += 1
                else:
                    state.records_created += 1
            state.pages_processed += 1
            await self.states.complete(state, cursor=final_cursor)
            await self.audits.record(
                self._audit(configuration, state, context, started_at, "success")
            )
            await self.db.commit()
            return state
        except Exception:
            await self.db.rollback()
            state = await self.states.get(context.organization_id, configuration.id, sync_key)
            if state is not None:
                await self.states.fail(
                    state,
                    error_code="connector_ingestion_failed",
                    error_summary="Connector record ingestion failed",
                )
                await self.audits.record(
                    self._audit(
                        configuration,
                        state,
                        context,
                        started_at,
                        "failure",
                        error_code="connector_ingestion_failed",
                    )
                )
                await self.db.commit()
            raise

    @staticmethod
    def _audit(configuration, state, context, started_at, outcome, error_code=None):
        completed_at = datetime.now(UTC)
        return ConnectorExecutionRecord(
            organization_id=context.organization_id,
            user_id=context.user_id,
            connector_configuration_id=configuration.id,
            sync_state_id=state.id,
            connector_name=configuration.stable_name,
            operation="sync",
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            source_type=configuration.connector_type,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=max(int((completed_at - started_at).total_seconds() * 1000), 0),
            page_count=state.pages_processed,
            result_count=state.records_processed,
            bytes_received=state.bytes_received,
            cache_status="miss",
            retry_count=state.retry_count,
            outcome=outcome,
            error_code=error_code,
            policy_decision="allow",
            external_transmission=True,
            classification=context.classification.value,
            credential_reference_used=configuration.credential_reference,
            metadata_json={"sync_key": state.sync_key},
        )
