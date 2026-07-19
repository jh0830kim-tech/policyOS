"""Provider-independent model request/response contracts and gateways."""

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.ai.domain import UsageMetadata
from app.ai.privacy import ProviderTransmissionContext


class ModelContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OutputFormat(StrEnum):
    JSON = "json"
    TEXT = "text"


class ModelRequest(ModelContract):
    system_prompt: str = Field(min_length=1, max_length=50_000)
    user_instruction: str = Field(min_length=1, max_length=10_000)
    structured_context: dict[str, Any] = Field(default_factory=dict)
    output_format: OutputFormat = OutputFormat.JSON
    output_schema: dict[str, Any] | None = None
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    model_id: str = Field(min_length=1, max_length=200)
    transmission_context: ProviderTransmissionContext | None = None


class ModelResponse(ModelContract):
    model_id: str = Field(min_length=1, max_length=200)
    transmission_context: ProviderTransmissionContext | None = None
    structured_output: dict[str, Any]
    summary: str | None = Field(default=None, max_length=2_000)
    usage: UsageMetadata = Field(default_factory=UsageMetadata)
    provider_request_id: str | None = Field(default=None, max_length=500)


class ModelErrorCode(StrEnum):
    CONFIGURATION = "configuration_error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CONNECTION = "connection_error"
    SERVER_ERROR = "server_error"
    INVALID_RESPONSE = "invalid_response"
    AUTHENTICATION = "authentication_error"
    PERMISSION_DENIED = "permission_denied"
    INVALID_REQUEST = "invalid_request"
    REFUSED = "refused"
    INCOMPLETE = "incomplete"
    POLICY_BLOCKED = "provider_policy_blocked"
    UNKNOWN = "unknown"


class ModelGatewayError(Exception):
    """Safe provider-neutral failure exposed to orchestration code."""

    def __init__(
        self,
        code: ModelErrorCode,
        message: str,
        *,
        retryable: bool,
        provider_request_id: str | None = None,
        retry_count: int = 0,
        latency_ms: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        self.code = code
        self.safe_message = message
        self.retryable = retryable
        self.provider_request_id = provider_request_id
        self.retry_count = retry_count
        self.latency_ms = latency_ms
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


class ModelTimeoutError(ModelGatewayError):
    def __init__(self) -> None:
        super().__init__(
            ModelErrorCode.TIMEOUT,
            "Model request timed out",
            retryable=True,
        )


class ModelConfigurationError(ModelGatewayError):
    def __init__(self, message: str = "No model provider is configured") -> None:
        super().__init__(
            ModelErrorCode.CONFIGURATION,
            message,
            retryable=False,
        )


@runtime_checkable
class ModelGateway(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a final structured response without exposing hidden reasoning."""
        ...


class FakeModelGateway:
    """Deterministic, network-free gateway injected into tests and local workflows."""

    def __init__(
        self,
        structured_output: dict[str, Any] | None = None,
        *,
        summary: str = "Deterministic fake response.",
        simulated_latency_seconds: float = 0,
        error: ModelGatewayError | None = None,
    ) -> None:
        self._structured_output = structured_output
        self._summary = summary
        self._simulated_latency_seconds = simulated_latency_seconds
        self._error = error
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if request.timeout_seconds <= self._simulated_latency_seconds:
            raise ModelTimeoutError
        if self._error is not None:
            raise self._error
        return ModelResponse(
            model_id=request.model_id,
            structured_output=(
                self._structured_output
                if self._structured_output is not None
                else _fake_structured_output(request.output_schema)
            ),
            summary=self._summary,
            usage=UsageMetadata(
                provider="fake",
                model=request.model_id,
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                duration_ms=int(self._simulated_latency_seconds * 1_000),
            ),
            provider_request_id="fake-request-1",
        )


class DisabledModelGateway:
    """Fails clearly when no real or fake provider was dependency-injected."""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise ModelConfigurationError


def _fake_structured_output(schema: dict[str, Any] | None) -> dict[str, Any]:
    """Build deterministic schema-shaped data for network-free application tests."""
    if schema is None:
        return {"result": "fake"}

    def value(node: dict[str, Any]) -> Any:
        if "$ref" in node:
            target: Any = schema
            for part in node["$ref"].removeprefix("#/").split("/"):
                target = target[part]
            return value(target)
        if "const" in node:
            return node["const"]
        if "enum" in node:
            return node["enum"][0]
        if "anyOf" in node:
            option = next(
                (item for item in node["anyOf"] if item.get("type") != "null"),
                node["anyOf"][0],
            )
            return value(option)
        node_type = node.get("type")
        if node_type == "object" or "properties" in node:
            properties = node.get("properties", {})
            required = node.get("required", properties.keys())
            return {
                name: value(properties[name]) if name in properties else "fake" for name in required
            }
        if node_type == "array":
            minimum = node.get("minItems", 0)
            return [value(node.get("items", {})) for _ in range(minimum)]
        if node_type == "integer":
            return max(1, int(node.get("minimum", 0)))
        if node_type == "number":
            return max(1.0, float(node.get("minimum", 0)))
        if node_type == "boolean":
            return False
        if node.get("format") == "uuid":
            return "00000000-0000-0000-0000-000000000001"
        if node.get("format") == "date-time":
            return "2026-01-01T00:00:00Z"
        return "fake"

    result = value(schema)
    return result if isinstance(result, dict) else {"result": result}
