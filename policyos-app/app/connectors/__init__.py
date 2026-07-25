"""Production connector foundation for external public-sector data sources."""

from app.connectors.cache import InMemoryConnectorCache
from app.connectors.client import DisabledConnectorClient, FakeConnectorClient, HTTPConnectorClient
from app.connectors.credentials import (
    DisabledCredentialProvider,
    EnvironmentCredentialProvider,
    FakeCredentialProvider,
)
from app.connectors.domain import (
    ConnectorCapability,
    ConnectorConfigurationError,
    ConnectorDefinition,
    ConnectorError,
    ConnectorHealthResult,
    ConnectorRequestContext,
    ConnectorStatus,
    ConnectorSyncCursor,
    ConnectorType,
)
from app.connectors.health import ConnectorHealthService
from app.connectors.ingestion import ConnectorIngestionResult, ConnectorIngestionService
from app.connectors.normalization import ExternalSourceRecord, normalize_external_record
from app.connectors.pagination import CursorPagination, OffsetPagination, PageNumberPagination
from app.connectors.parsing import (
    JsonConnectorResponseParser,
    PaginationMetadata,
    ParsedConnectorItem,
    ParsedConnectorResponse,
    SourceFreshnessMetadata,
    TextConnectorResponseParser,
    XmlConnectorResponseParser,
)
from app.connectors.registry import ConnectorRegistry
from app.connectors.resilience import RetryPolicy
from app.connectors.security import ConnectorSecurityPolicy
from app.connectors.sync import ConnectorSyncService, ConnectorSyncState

__all__ = [
    "ConnectorCapability",
    "ConnectorConfigurationError",
    "ConnectorDefinition",
    "ConnectorError",
    "ConnectorHealthResult",
    "ConnectorHealthService",
    "ConnectorIngestionResult",
    "ConnectorIngestionService",
    "ConnectorRegistry",
    "ConnectorRequestContext",
    "ConnectorSecurityPolicy",
    "ConnectorStatus",
    "ConnectorSyncCursor",
    "ConnectorSyncService",
    "ConnectorSyncState",
    "ConnectorType",
    "CursorPagination",
    "DisabledConnectorClient",
    "DisabledCredentialProvider",
    "EnvironmentCredentialProvider",
    "ExternalSourceRecord",
    "FakeConnectorClient",
    "FakeCredentialProvider",
    "HTTPConnectorClient",
    "InMemoryConnectorCache",
    "JsonConnectorResponseParser",
    "OffsetPagination",
    "PageNumberPagination",
    "ParsedConnectorItem",
    "ParsedConnectorResponse",
    "PaginationMetadata",
    "RetryPolicy",
    "SourceFreshnessMetadata",
    "TextConnectorResponseParser",
    "XmlConnectorResponseParser",
    "normalize_external_record",
]
