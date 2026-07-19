"""Provider-independent model request/response contracts and gateways."""

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.ai.domain import UsageMetadata


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


class ModelResponse(ModelContract):
    model_id: str = Field(min_length=1, max_length=200)
    structured_output: dict[str, Any]
    summary: str | None = Field(default=None, max_length=2_000)
    usage: UsageMetadata = Field(default_factory=UsageMetadata)
    provider_request_id: str | None = Field(default=None, max_length=500)


class ModelErrorCode(StrEnum):
    CONFIGURATION = "configuration_error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_RESPONSE = "invalid_response"
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
    ) -> None:
        self.code = code
        self.safe_message = message
        self.retryable = retryable
        self.provider_request_id = provider_request_id
        super().__init__(message)


class ModelTimeoutError(ModelGatewayError):
    def __init__(self) -> None:
        super().__init__(
            ModelErrorCode.TIMEOUT,
            "Model request timed out",
            retryable=True,
        )


class ModelConfigurationError(ModelGatewayError):
    def __init__(self) -> None:
        super().__init__(
            ModelErrorCode.CONFIGURATION,
            "No model provider is configured",
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
        self._structured_output = structured_output or {"result": "fake"}
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
            structured_output=self._structured_output,
            summary=self._summary,
            usage=UsageMetadata(
                model=request.model_id,
                input_tokens=10,
                output_tokens=5,
                duration_ms=int(self._simulated_latency_seconds * 1_000),
            ),
            provider_request_id="fake-request-1",
        )


class DisabledModelGateway:
    """Fails clearly when no real or fake provider was dependency-injected."""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise ModelConfigurationError

