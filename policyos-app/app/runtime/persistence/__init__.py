"""CP7 PostgreSQL runtime persistence implementations."""

from app.models.runtime_logical_result import (
    RuntimeLogicalExecutionResultRecord,
    RuntimeLogicalExecutionResultRevisionRecord,
)
from app.runtime.persistence.active_transaction import (
    SQLAlchemyRuntimeApiActiveTransactionPersistence,
    SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory,
)
from app.runtime.persistence.delivery_repositories import (
    SQLAlchemyRuntimeEffectDueRepository,
    SQLAlchemyRuntimeEffectLifecycleTransaction,
)
from app.runtime.persistence.delivery_serialization import (
    deserialize_delivery_model,
    serialize_delivery_model,
)
from app.runtime.persistence.delivery_transaction import (
    SQLAlchemyRuntimeEffectAtomicTransaction,
)
from app.runtime.persistence.errors import (
    RuntimeEffectPersistenceConflictError,
    RuntimePersistenceConflictError,
    RuntimePersistenceError,
    RuntimePersistenceSerializationError,
    RuntimePersistenceTransactionError,
    RuntimeRegistryPersistenceBindingError,
    RuntimeRegistryPersistenceNotFoundError,
)
from app.runtime.persistence.logical_result_repositories import (
    SQLAlchemyRuntimeLogicalExecutionResultRepository,
)
from app.runtime.persistence.logical_result_serialization import (
    deserialize_logical_execution_result,
    serialize_logical_execution_result,
)
from app.runtime.persistence.models import (
    RUNTIME_EFFECT_PERSISTENCE_TABLES,
    RUNTIME_PERSISTENCE_TABLES,
    RuntimeEffect,
    RuntimeEffectLifecycleHead,
    RuntimeEffectLifecycleRevision,
    RuntimeEffectReconciliationObservationRecord,
    RuntimeRecordHead,
    RuntimeRecordRevision,
    RuntimeTransactionRecord,
)
from app.runtime.persistence.registry_repositories import SQLAlchemyRuntimeRegistryRepository
from app.runtime.persistence.registry_serialization import (
    RuntimeRegistryPayload,
    RuntimeRegistryPayloadType,
    deserialize_registry_payload,
    serialize_registry_payload,
    validate_registry_graph,
)
from app.runtime.persistence.repositories import (
    SQLAlchemyExecutionPlanRepository,
    SQLAlchemyExecutionRequestRepository,
    SQLAlchemyExecutionResultRepository,
    SQLAlchemyExecutionStateRepository,
    SQLAlchemyRuntimeAdmissionRepository,
    SQLAlchemyRuntimeAuditRepository,
    SQLAlchemyRuntimeIdempotencyRepository,
    SQLAlchemyRuntimeOutboxRepository,
    SQLAlchemyRuntimePermitRepository,
)
from app.runtime.persistence.serialization import (
    RuntimePersistenceRecord,
    RuntimePersistenceRecordMetadata,
    RuntimePersistenceRecordType,
    deserialize_runtime_record,
    metadata_for,
    serialize_runtime_record,
)
from app.runtime.persistence.transaction import SQLAlchemyRuntimeTransaction
from app.runtime.persistence.validation import (
    validate_loaded_record,
    validate_persistence_read_request,
    validate_persistence_write,
)

RUNTIME_LOGICAL_RESULT_PERSISTENCE_TABLES = (
    RuntimeLogicalExecutionResultRecord.__table__,
    RuntimeLogicalExecutionResultRevisionRecord.__table__,
)

__all__ = (
    "RUNTIME_EFFECT_PERSISTENCE_TABLES",
    "RUNTIME_LOGICAL_RESULT_PERSISTENCE_TABLES",
    "RUNTIME_PERSISTENCE_TABLES",
    "RuntimeEffect",
    "RuntimeEffectLifecycleHead",
    "RuntimeEffectLifecycleRevision",
    "RuntimeEffectPersistenceConflictError",
    "RuntimeEffectReconciliationObservationRecord",
    "RuntimePersistenceConflictError",
    "RuntimePersistenceError",
    "RuntimePersistenceRecord",
    "RuntimePersistenceRecordMetadata",
    "RuntimePersistenceRecordType",
    "RuntimePersistenceSerializationError",
    "RuntimePersistenceTransactionError",
    "RuntimeRegistryPayload",
    "RuntimeRegistryPayloadType",
    "RuntimeRegistryPersistenceBindingError",
    "RuntimeRegistryPersistenceNotFoundError",
    "RuntimeRecordHead",
    "RuntimeRecordRevision",
    "RuntimeTransactionRecord",
    "SQLAlchemyExecutionPlanRepository",
    "SQLAlchemyExecutionRequestRepository",
    "SQLAlchemyExecutionResultRepository",
    "SQLAlchemyExecutionStateRepository",
    "SQLAlchemyRuntimeEffectAtomicTransaction",
    "SQLAlchemyRuntimeEffectDueRepository",
    "SQLAlchemyRuntimeEffectLifecycleTransaction",
    "SQLAlchemyRuntimeAdmissionRepository",
    "SQLAlchemyRuntimeAuditRepository",
    "SQLAlchemyRuntimeApiActiveTransactionPersistence",
    "SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory",
    "SQLAlchemyRuntimeIdempotencyRepository",
    "SQLAlchemyRuntimeLogicalExecutionResultRepository",
    "SQLAlchemyRuntimeOutboxRepository",
    "SQLAlchemyRuntimePermitRepository",
    "SQLAlchemyRuntimeRegistryRepository",
    "SQLAlchemyRuntimeTransaction",
    "deserialize_delivery_model",
    "deserialize_logical_execution_result",
    "deserialize_runtime_record",
    "deserialize_registry_payload",
    "metadata_for",
    "serialize_delivery_model",
    "serialize_logical_execution_result",
    "serialize_runtime_record",
    "serialize_registry_payload",
    "validate_loaded_record",
    "validate_persistence_read_request",
    "validate_persistence_write",
    "validate_registry_graph",
)
