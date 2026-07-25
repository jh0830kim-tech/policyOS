"""Safe application services for connector persistence lifecycles."""

from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.credentials import parse_credential_reference
from app.connectors.domain import ConnectorConfigurationError
from app.connectors.repositories import (
    ConnectorAuditRepository,
    ConnectorConfigurationRepository,
    ConnectorHealthStateRepository,
    ConnectorSyncStateRepository,
)
from app.connectors.security import ConnectorSecurityPolicy
from app.models.connectors import ConnectorConfiguration, ConnectorExecutionRecord

FORBIDDEN_KEYS = {"secret", "token", "password", "authorization", "raw_response", "api_key"}


class ConnectorServiceError(Exception):
    def __init__(self, code: str, safe_message: str, http_status: int = 400) -> None:
        self.code = code
        self.safe_message = safe_message
        self.http_status = http_status
        super().__init__(safe_message)


def safe_metadata(value):
    def inspect(item):
        if isinstance(item, dict):
            for key, nested in item.items():
                if any(term in str(key).lower() for term in FORBIDDEN_KEYS):
                    raise ConnectorServiceError(
                        "unsafe_metadata", "Connector metadata is not allowed"
                    )
                inspect(nested)
        elif isinstance(item, list):
            for nested in item:
                inspect(nested)

    inspect(value)
    return value


class ConnectorConfigurationService:
    def __init__(self, db: AsyncSession, security: ConnectorSecurityPolicy) -> None:
        self.db = db
        self.repository = ConnectorConfigurationRepository(db)
        self.security = security

    def validate_endpoint(self, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.query or parsed.username or parsed.password:
            raise ConnectorServiceError("unsafe_endpoint", "Connector endpoint is not allowed")
        try:
            allowed = self.security.validate_url(value)
        except Exception as exc:
            raise ConnectorServiceError(
                "unsafe_endpoint", "Connector endpoint is not allowed"
            ) from exc
        if not allowed:
            raise ConnectorServiceError("unsafe_endpoint", "Connector endpoint is not allowed")
        return value

    @staticmethod
    def validate_reference(value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parse_credential_reference(value)
        except ConnectorConfigurationError as exc:
            raise ConnectorServiceError(
                "invalid_credential_reference", "Credential reference is invalid"
            ) from exc
        return value

    async def create(self, organization_id, user_id, payload):
        if await self.repository.get_by_stable_name(organization_id, payload.stable_name):
            raise ConnectorServiceError("connector_duplicate", "Connector already exists", 409)
        excluded = {
            "endpoint_reference",
            "supported_operations",
            "allowed_classifications",
            "metadata_json",
        }
        item = ConnectorConfiguration(
            organization_id=organization_id,
            created_by=user_id,
            enabled=False,
            endpoint_reference=self.validate_endpoint(payload.endpoint_reference),
            credential_reference=self.validate_reference(payload.credential_reference),
            supported_operations=[value.value for value in payload.supported_operations],
            allowed_classifications=[value.value for value in payload.allowed_classifications],
            metadata_json=safe_metadata(payload.metadata_json),
            **payload.model_dump(exclude=excluded | {"credential_reference"}),
        )
        await self.repository.create(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def require(self, organization_id, stable_name):
        item = await self.repository.get_by_stable_name(organization_id, stable_name)
        if item is None:
            raise ConnectorServiceError("connector_not_found", "Connector not found", 404)
        return item

    async def update(self, organization_id, stable_name, payload):
        item = await self.require(organization_id, stable_name)
        changes = payload.model_dump(exclude_unset=True)
        if "endpoint_reference" in changes:
            changes["endpoint_reference"] = self.validate_endpoint(changes["endpoint_reference"])
        if "credential_reference" in changes:
            changes["credential_reference"] = self.validate_reference(
                changes["credential_reference"]
            )
        if "metadata_json" in changes:
            changes["metadata_json"] = safe_metadata(changes["metadata_json"])
        for key in ("supported_operations", "allowed_classifications"):
            if key in changes:
                changes[key] = [
                    value.value if hasattr(value, "value") else value for value in changes[key]
                ]
        for key, value in changes.items():
            setattr(item, key, value)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def set_enabled(self, organization_id, stable_name, enabled):
        item = await self.require(organization_id, stable_name)
        if enabled and not item.credential_reference:
            raise ConnectorServiceError("connector_not_ready", "Credential reference is required")
        item.enabled = enabled
        await self.db.commit()
        await self.db.refresh(item)
        return item


class ConnectorSyncStateService:
    COUNTERS = {
        "records_processed",
        "records_created",
        "records_updated",
        "records_skipped",
        "records_failed",
        "pages_processed",
        "bytes_received",
        "retry_count",
        "partial_failure_count",
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = ConnectorSyncStateRepository(db)

    async def start(self, organization_id, configuration_id, sync_key, correlation_id):
        state = await self.repository.start(
            organization_id, configuration_id, sync_key, correlation_id
        )
        await self.db.commit()
        await self.db.refresh(state)
        return state

    async def progress(self, state, *, cursor=None, **counters):
        if state.status != "running":
            raise ConnectorServiceError("sync_not_running", "Connector sync is not running", 409)
        state.pending_cursor = cursor
        for key, value in counters.items():
            if key in self.COUNTERS:
                setattr(state, key, max(int(value), 0))
        await self.db.flush()
        return state

    async def complete(self, state, *, cursor=None, partial=False):
        await self.repository.complete(state, cursor=cursor, partial=partial)
        await self.db.commit()
        await self.db.refresh(state)
        return state

    async def fail(self, state, *, code, summary):
        await self.repository.fail(state, error_code=code, error_summary=summary)
        await self.db.commit()
        return state

    async def cancel(self, state):
        if state.status != "running":
            raise ConnectorServiceError("sync_not_running", "Connector sync is not running", 409)
        state.status = "cancelled"
        state.pending_cursor = None
        state.last_completed_at = datetime.now(UTC)
        await self.db.commit()
        return state

    async def recover_stale(self, organization_id, stale_after_seconds):
        states = await self.repository.find_stale_running(organization_id, stale_after_seconds)
        for state in states:
            await self.repository.fail(
                state,
                error_code="stale_running",
                error_summary="Stale running sync recovered",
            )
        await self.db.commit()
        return len(states)


class ConnectorHealthPersistenceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = ConnectorHealthStateRepository(db)

    async def persist(
        self, organization_id, configuration_id, *, status, latency_ms, error_code=None
    ):
        state = await self.repository.upsert(
            organization_id,
            configuration_id,
            status=status,
            latency_ms=latency_ms,
            error_code=error_code,
        )
        if state.consecutive_failure_count >= 3 and status not in {"disabled", "misconfigured"}:
            state.status = "unavailable"
        await self.db.commit()
        return state


class ConnectorExecutionAuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = ConnectorAuditRepository(db)

    async def record(self, **values):
        values["metadata_json"] = safe_metadata(values.get("metadata_json", {}))
        item = ConnectorExecutionRecord(**values)
        await self.repository.record(item)
        await self.db.flush()
        return item
