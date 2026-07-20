"""Governed MCP domain contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.privacy import DataClassification


class MCPModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MCPTransportType(StrEnum):
    REMOTE = "remote"
    LOCAL_PROCESS = "local_process"
    FAKE = "fake"
    DISABLED = "disabled"


class MCPServerStatus(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class MCPServerCapability(StrEnum):
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    HEALTH = "health"


class MCPErrorCode(StrEnum):
    DISABLED = "mcp_disabled"
    UNKNOWN_SERVER = "mcp_unknown_server"
    UNKNOWN_TOOL = "mcp_unknown_tool"
    PERMISSION = "mcp_permission_denied"
    POLICY = "mcp_policy_denied"
    APPROVAL = "mcp_approval_required"
    VALIDATION = "mcp_validation_error"
    TIMEOUT = "mcp_timeout"
    RATE_LIMIT = "mcp_rate_limit"
    CONNECTION = "mcp_connection_error"
    AUTHENTICATION = "mcp_authentication_error"
    RESULT = "mcp_invalid_result"
    RESULT_TOO_LARGE = "mcp_result_too_large"


class MCPError(RuntimeError):
    def __init__(
        self,
        code: MCPErrorCode,
        message: str,
        *,
        retryable: bool = False,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after


class MCPToolDefinition(MCPModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    description: str = Field(max_length=1000)
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    read_only: bool = True
    consequential: bool = False
    required_permission: str = "mcp.execute"
    timeout_seconds: float | None = Field(default=None, gt=0, le=300)


class MCPResourceDefinition(MCPModel):
    uri_template: str
    name: str
    description: str = ""
    mime_types: tuple[str, ...] = ("application/json",)


class MCPPromptDefinition(MCPModel):
    name: str
    description: str = ""
    argument_schema: dict[str, object] = Field(default_factory=dict)


class MCPServerDefinition(MCPModel):
    stable_name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,99}$")
    display_name: str
    description: str = ""
    version: str
    transport_type: MCPTransportType
    endpoint: str | None = None
    command_metadata: dict[str, object] = Field(default_factory=dict)
    enabled: bool = True
    read_only: bool = True
    allowed_organizations: frozenset[UUID] | None = None
    allowed_classifications: frozenset[DataClassification] = frozenset(
        {DataClassification.PUBLIC, DataClassification.INTERNAL}
    )
    allowed_tools: frozenset[str] = frozenset()
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    max_result_bytes: int = Field(default=1_000_000, ge=1, le=50_000_000)
    requires_human_approval: bool = False
    credential_reference: str | None = None
    health_status: MCPServerStatus = MCPServerStatus.UNKNOWN
    capabilities: frozenset[MCPServerCapability] = frozenset({MCPServerCapability.TOOLS})
    metadata: dict[str, object] = Field(default_factory=dict)


class MCPExecutionContext(MCPModel):
    user_id: UUID
    organization_id: UUID
    membership_id: UUID
    task_id: UUID | None = None
    agent_run_id: UUID | None = None
    work_package_id: UUID | None = None
    data_classification: DataClassification = DataClassification.INTERNAL
    permissions: frozenset[str]
    request_id: UUID
    correlation_id: str = Field(max_length=200)
    deadline: datetime | None = None
    human_approval_reference: str | None = None
    source_purpose: str = Field(max_length=500)
    membership_active: bool = True
    confidential_external_allowed: bool = False


class MCPToolCallRequest(MCPModel):
    server_name: str
    tool_name: str
    arguments: dict[str, object]
    context: MCPExecutionContext


class MCPToolCallResult(MCPModel):
    content: object
    content_type: str = "application/json"
    result_size: int = Field(ge=0)
    server_request_id: str | None = None
    classification: DataClassification
    warnings: tuple[str, ...] = ()
    suspicious: bool = False
    untrusted: bool = True
    retry_count: int = 0
    from_cache: bool = False
    stale: bool = False


class MCPResourceReadRequest(MCPModel):
    server_name: str
    resource_uri: str
    context: MCPExecutionContext


class MCPResourceReadResult(MCPModel):
    content: object
    content_type: str
    result_size: int
    classification: DataClassification
    warnings: tuple[str, ...] = ()
    untrusted: bool = True


class MCPAuditMetadata(MCPModel):
    audit_id: UUID
    organization_id: UUID
    user_id: UUID
    server_name: str
    server_version: str
    tool_name: str | None = None
    resource_uri: str | None = None
    action_type: str
    request_id: UUID
    correlation_id: str
    data_classification: DataClassification
    permission_decision: str
    policy_decision: str
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    retry_count: int
    result_size: int
    success: bool
    error_code: str | None = None
    human_approval_required: bool
    human_approval_reference: str | None = None
    redaction_applied: bool = False
    external_transmission: bool
    source_freshness: dict[str, object] = Field(default_factory=dict)


class MCPServerHealth(MCPModel):
    server_name: str
    status: MCPServerStatus
    last_checked_at: datetime
    last_success_at: datetime | None = None
    failure_count: int = 0
    last_error_code: str | None = None
    latency_ms: int = 0
    capabilities_hash: str
    server_version: str
