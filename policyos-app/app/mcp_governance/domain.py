"""Immutable, provider-neutral MCP registration and negotiation contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.mcp_governance.errors import (
    McpCapabilityError,
    McpExtensionError,
    McpProtocolVersionError,
)

BoundedId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")]
ProtocolVersion = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$")]


def canonical(value: tuple, name: str, maximum: int = 50) -> tuple:
    if not value or len(value) > maximum or tuple(sorted(set(value), key=str)) != value:
        raise ValueError(f"{name} must be non-empty, canonical, unique, and bounded")
    return value


class McpTransportType(StrEnum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"
    SSE_LEGACY = "sse_legacy"
    MANAGED_INTERNAL = "managed_internal"
    CUSTOM_MANAGED = "custom_managed"


class McpCapability(StrEnum):
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    LOGGING = "logging"
    SAMPLING = "sampling"
    ROOTS = "roots"
    COMPLETIONS = "completions"
    RESOURCE_SUBSCRIPTIONS = "resource_subscriptions"
    TOOL_LIST_CHANGED = "tool_list_changed"
    RESOURCE_LIST_CHANGED = "resource_list_changed"
    PROMPT_LIST_CHANGED = "prompt_list_changed"


class McpAuthenticationScheme(StrEnum):
    NONE = "none"
    STATIC_BEARER_REFERENCE = "static_bearer_reference"
    OAUTH_2_1 = "oauth_2_1"
    CLIENT_CREDENTIALS = "client_credentials"
    MTLS = "mtls"
    WORKLOAD_IDENTITY = "workload_identity"
    CUSTOM_MANAGED = "custom_managed"


class McpCompatibilityStatus(StrEnum):
    UNKNOWN = "unknown"
    DISCOVERED = "discovered"
    NEGOTIATION_REQUIRED = "negotiation_required"
    CONTRACT_TESTING = "contract_testing"
    COMPATIBLE = "compatible"
    DEGRADED = "degraded"
    INCOMPATIBLE = "incompatible"
    QUARANTINED = "quarantined"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class McpCompatibilityReason(StrEnum):
    PROTOCOL_VERSION_UNSUPPORTED = "protocol_version_unsupported"
    REQUIRED_CAPABILITY_MISSING = "required_capability_missing"
    EXTENSION_VERSION_MISMATCH = "extension_version_mismatch"
    AUTH_SCHEME_UNSUPPORTED = "auth_scheme_unsupported"
    TOOL_SCHEMA_CHANGED = "tool_schema_changed"
    TOOL_CATALOG_REVISION_MISMATCH = "tool_catalog_revision_mismatch"
    CONTRACT_TEST_FAILED = "contract_test_failed"
    SECURITY_POLICY_REJECTED = "security_policy_rejected"
    MANUAL_APPROVAL_REQUIRED = "manual_approval_required"
    LEGACY_ONLY = "legacy_only"
    DEPRECATED_PROTOCOL = "deprecated_protocol"
    UNKNOWN_COMPATIBILITY = "unknown_compatibility"


class McpExtensionDeclaration(ExecutionModel):
    extension_id: BoundedId
    extension_version: BoundedId
    required: bool
    schema_hash: BoundedId | None = None
    compatibility_status: McpCompatibilityStatus
    reason_codes: tuple[McpCompatibilityReason, ...] = ()

    @field_validator("reason_codes")
    @classmethod
    def reasons(cls, v):
        return canonical(v, "reason codes") if v else v


class McpServerRegistration(ExecutionModel):
    mcp_server_id: BoundedId
    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    deployment_id: BoundedId
    provider_name: BoundedId
    transport_type: McpTransportType
    endpoint_reference: BoundedId
    supported_protocol_versions: tuple[ProtocolVersion, ...]
    preferred_protocol_version: ProtocolVersion
    verified_protocol_versions: tuple[ProtocolVersion, ...] = ()
    deprecated_protocol_versions: tuple[ProtocolVersion, ...] = ()
    declared_capabilities: tuple[McpCapability, ...]
    verified_capabilities: tuple[McpCapability, ...] = ()
    required_capabilities: tuple[McpCapability, ...] = ()
    supported_extensions: tuple[McpExtensionDeclaration, ...] = ()
    authentication_scheme: McpAuthenticationScheme
    credential_reference: BoundedId | None = None
    audience_reference: BoundedId | None = None
    tool_catalog_revision: BoundedId
    compatibility_status: McpCompatibilityStatus
    compatibility_reason_codes: tuple[McpCompatibilityReason, ...] = ()
    enabled: bool
    registry_revision: int = Field(ge=1)
    created_at: datetime

    @field_validator("supported_protocol_versions")
    @classmethod
    def protocols(cls, v):
        return canonical(v, "supported protocol versions")

    @field_validator(
        "verified_protocol_versions",
        "deprecated_protocol_versions",
        "declared_capabilities",
        "verified_capabilities",
        "required_capabilities",
        "compatibility_reason_codes",
    )
    @classmethod
    def canonical_optional(cls, v, info):
        return canonical(v, info.field_name) if v else v

    @field_validator("supported_extensions")
    @classmethod
    def extensions(cls, v):
        if tuple(sorted(v, key=lambda x: x.extension_id)) != v or len(
            {x.extension_id for x in v}
        ) != len(v):
            raise ValueError("extensions must be canonical and unique")
        return v

    @field_validator("created_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "created_at")

    @model_validator(mode="after")
    def consistent(self):
        supported = set(self.supported_protocol_versions)
        if self.preferred_protocol_version not in supported:
            raise ValueError("preferred protocol must be supported")
        if not set(self.verified_protocol_versions) <= supported:
            raise ValueError("verified protocols must be supported")
        if not set(self.deprecated_protocol_versions) <= supported:
            raise ValueError("deprecated protocols must be supported")
        if set(self.verified_protocol_versions) & set(self.deprecated_protocol_versions):
            raise ValueError("verified and deprecated protocols cannot overlap")
        if not set(self.verified_capabilities) <= set(self.declared_capabilities):
            raise ValueError("verified capabilities must be declared")
        if not set(self.required_capabilities) <= set(self.declared_capabilities):
            raise ValueError("required capabilities must be declared")
        if self.authentication_scheme is McpAuthenticationScheme.NONE and self.credential_reference:
            raise ValueError("unauthenticated registration cannot reference credentials")
        if any(
            marker in self.endpoint_reference.lower()
            for marker in ("token=", "password=", "secret=", "@")
        ):
            raise ValueError("endpoint reference may not contain credentials")
        return self


class McpToolRegistration(ExecutionModel):
    tool_id: BoundedId
    mcp_server_id: BoundedId
    tool_name: BoundedId
    operation: BoundedId
    tool_catalog_revision: BoundedId
    tool_schema_revision: BoundedId
    input_schema_hash: BoundedId | None = None
    output_schema_hash: BoundedId | None = None
    required_capabilities: tuple[McpCapability, ...] = (McpCapability.TOOLS,)
    read_only: bool
    external_side_effect: bool
    supports_internal_use: bool
    supports_external_transmission: bool
    enabled: bool
    created_at: datetime

    @field_validator("required_capabilities")
    @classmethod
    def caps(cls, v):
        return canonical(v, "required capabilities")

    @field_validator("created_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "created_at")

    @model_validator(mode="after")
    def semantics(self):
        if self.read_only and self.external_side_effect:
            raise ValueError("read-only tool cannot declare an external side effect")
        return self


class McpNegotiationResult(ExecutionModel):
    negotiation_id: UUID
    mcp_server_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    requested_protocol_version: ProtocolVersion
    negotiated_protocol_version: ProtocolVersion
    declared_server_capabilities: tuple[McpCapability, ...]
    negotiated_capabilities: tuple[McpCapability, ...]
    negotiated_extensions: tuple[McpExtensionDeclaration, ...] = ()
    authentication_scheme: McpAuthenticationScheme
    tool_catalog_revision: BoundedId
    compatibility_status: McpCompatibilityStatus
    reason_codes: tuple[McpCompatibilityReason, ...] = ()
    negotiated_at: datetime

    @field_validator("declared_server_capabilities", "negotiated_capabilities")
    @classmethod
    def caps(cls, v, info):
        return canonical(v, info.field_name)

    @field_validator("reason_codes")
    @classmethod
    def reasons(cls, v):
        return canonical(v, "reason codes") if v else v

    @field_validator("negotiated_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "negotiated_at")

    @model_validator(mode="after")
    def subset(self):
        if not set(self.negotiated_capabilities) <= set(self.declared_server_capabilities):
            raise ValueError("negotiated capabilities must be declared")
        return self


def resolve_mcp_protocol_version(
    *,
    client_supported_versions: tuple[str, ...],
    server_registration: McpServerRegistration,
    requested_version: str,
) -> str:
    canonical(client_supported_versions, "client supported versions")
    if (
        requested_version not in client_supported_versions
        or requested_version not in server_registration.supported_protocol_versions
    ):
        raise McpProtocolVersionError("requested MCP protocol version is unsupported")
    return requested_version


def create_negotiation_result(
    *,
    registration: McpServerRegistration,
    registry_id: UUID,
    registry_revision: int,
    negotiation_id: UUID,
    client_supported_versions: tuple[str, ...],
    requested_version: str,
    negotiated_capabilities: tuple[McpCapability, ...],
    negotiated_extensions: tuple[McpExtensionDeclaration, ...],
    supported_authentication_schemes: tuple[McpAuthenticationScheme, ...],
    allow_optional_extension_degradation: bool,
    negotiated_at: datetime,
) -> McpNegotiationResult:
    if registration.registry_revision != registry_revision:
        raise McpProtocolVersionError("registry revision mismatch")
    protocol = resolve_mcp_protocol_version(
        client_supported_versions=client_supported_versions,
        server_registration=registration,
        requested_version=requested_version,
    )
    if registration.authentication_scheme not in supported_authentication_schemes:
        raise McpProtocolVersionError("authentication scheme unsupported")
    if not set(registration.required_capabilities) <= set(negotiated_capabilities):
        raise McpCapabilityError("required MCP capability is missing")
    by_id = {x.extension_id: x for x in negotiated_extensions}
    degraded = False
    for declared in registration.supported_extensions:
        actual = by_id.get(declared.extension_id)
        mismatch = actual is None or actual.extension_version != declared.extension_version
        if mismatch and declared.required:
            raise McpExtensionError("required MCP extension is missing or incompatible")
        if mismatch:
            if not allow_optional_extension_degradation:
                raise McpExtensionError("optional MCP extension mismatch was not accepted")
            degraded = True
    return McpNegotiationResult(
        negotiation_id=negotiation_id,
        mcp_server_id=registration.mcp_server_id,
        registry_id=registry_id,
        registry_revision=registry_revision,
        requested_protocol_version=requested_version,
        negotiated_protocol_version=protocol,
        declared_server_capabilities=registration.declared_capabilities,
        negotiated_capabilities=negotiated_capabilities,
        negotiated_extensions=negotiated_extensions,
        authentication_scheme=registration.authentication_scheme,
        tool_catalog_revision=registration.tool_catalog_revision,
        compatibility_status=McpCompatibilityStatus.DEGRADED
        if degraded
        else McpCompatibilityStatus.COMPATIBLE,
        reason_codes=(McpCompatibilityReason.EXTENSION_VERSION_MISMATCH,) if degraded else (),
        negotiated_at=negotiated_at,
    )
