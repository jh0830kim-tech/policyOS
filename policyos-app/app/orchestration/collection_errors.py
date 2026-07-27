"""Stable, payload-safe assignment work-product collection errors."""

from app.execution.errors import ExecutionDomainError


class WorkProductCollectionError(ExecutionDomainError):
    code = "work_product_collection_error"


class CollectionValidationError(WorkProductCollectionError):
    code = "work_product_collection_validation"


class CollectionStateError(CollectionValidationError):
    code = "work_product_collection_state"


class CollectionIdentityMismatchError(CollectionValidationError):
    code = "work_product_collection_identity_mismatch"


class CollectionTenantMismatchError(CollectionIdentityMismatchError):
    code = "work_product_collection_tenant_mismatch"


class CollectionClassificationMismatchError(CollectionIdentityMismatchError):
    code = "work_product_collection_classification_mismatch"


class CollectionDispatchMismatchError(CollectionIdentityMismatchError):
    code = "work_product_collection_dispatch_mismatch"


class CollectionOutputTypeMismatchError(CollectionValidationError):
    code = "work_product_collection_output_type_mismatch"


class CollectionRoleMismatchError(CollectionValidationError):
    code = "work_product_collection_role_mismatch"


class CollectionContentError(CollectionValidationError):
    code = "work_product_collection_content"


class CollectionReferenceError(CollectionValidationError):
    code = "work_product_collection_reference"


class CollectionDuplicateError(CollectionValidationError):
    code = "work_product_collection_duplicate"


class NonCollectableTargetError(CollectionValidationError):
    code = "work_product_collection_non_collectable_target"
