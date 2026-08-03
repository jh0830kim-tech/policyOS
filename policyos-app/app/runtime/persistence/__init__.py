"""CP7 PostgreSQL runtime persistence implementations."""

from app.runtime.persistence.errors import (
    RuntimePersistenceConflictError,
    RuntimePersistenceError,
    RuntimePersistenceSerializationError,
    RuntimePersistenceTransactionError,
)
from app.runtime.persistence.models import (
    RUNTIME_PERSISTENCE_TABLES,
    RuntimeRecordHead,
    RuntimeRecordRevision,
    RuntimeTransactionRecord,
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

__all__ = (
    "RUNTIME_PERSISTENCE_TABLES",
    "RuntimePersistenceConflictError",
    "RuntimePersistenceError",
    "RuntimePersistenceRecord",
    "RuntimePersistenceRecordMetadata",
    "RuntimePersistenceRecordType",
    "RuntimePersistenceSerializationError",
    "RuntimePersistenceTransactionError",
    "RuntimeRecordHead",
    "RuntimeRecordRevision",
    "RuntimeTransactionRecord",
    "SQLAlchemyExecutionPlanRepository",
    "SQLAlchemyExecutionRequestRepository",
    "SQLAlchemyExecutionResultRepository",
    "SQLAlchemyExecutionStateRepository",
    "SQLAlchemyRuntimeAdmissionRepository",
    "SQLAlchemyRuntimeAuditRepository",
    "SQLAlchemyRuntimeIdempotencyRepository",
    "SQLAlchemyRuntimeOutboxRepository",
    "SQLAlchemyRuntimePermitRepository",
    "SQLAlchemyRuntimeTransaction",
    "deserialize_runtime_record",
    "metadata_for",
    "serialize_runtime_record",
    "validate_loaded_record",
    "validate_persistence_read_request",
    "validate_persistence_write",
)
