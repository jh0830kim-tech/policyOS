"""Stable, payload-safe Secretary integration errors."""

from app.execution.errors import ExecutionDomainError


class SecretaryIntegrationError(ExecutionDomainError):
    code = "secretary_integration_error"


class IntegrationValidationError(SecretaryIntegrationError):
    code = "secretary_integration_validation"


class IntegrationActorError(IntegrationValidationError):
    code = "secretary_integration_actor"


class IntegrationIdentityMismatchError(IntegrationValidationError):
    code = "secretary_integration_identity_mismatch"


class IntegrationTenantMismatchError(IntegrationIdentityMismatchError):
    code = "secretary_integration_tenant_mismatch"


class IntegrationClassificationMismatchError(IntegrationIdentityMismatchError):
    code = "secretary_integration_classification_mismatch"


class IntegrationPlanMismatchError(IntegrationIdentityMismatchError):
    code = "secretary_integration_plan_mismatch"


class IntegrationProductMismatchError(IntegrationValidationError):
    code = "secretary_integration_product_mismatch"


class IntegrationDuplicateProductError(IntegrationProductMismatchError):
    code = "secretary_integration_duplicate_product"


class IntegrationLineageError(IntegrationProductMismatchError):
    code = "secretary_integration_lineage"


class UnsupportedIntegrationProductError(IntegrationProductMismatchError):
    code = "secretary_integration_unsupported_product"
