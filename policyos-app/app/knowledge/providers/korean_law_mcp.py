"""Safe Korean Law MCP request and response boundary.

No transport is constructed here. A governed or fake gateway must be injected.
Legal evidence and citation mapping intentionally remain outside Task 4.3.
"""

from __future__ import annotations

import ipaddress
import json
import re
from datetime import date
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.knowledge.providers.domain import ProviderModel
from app.knowledge.providers.korean_law import (
    KOREAN_LAW_PROVIDER_NAME,
    KOREAN_LAW_SOURCE_TYPES,
)
from app.knowledge.providers.korean_law_tools import (
    KoreanLawMcpCapabilityMismatchError,
    KoreanLawMcpCapabilityResolver,
    KoreanLawMcpOperation,
    KoreanLawMcpToolNotFoundError,
    KoreanLawMcpToolRegistry,
)
from app.mcp.domain import (
    MCPError,
    MCPErrorCode,
    MCPExecutionContext,
    MCPToolCallRequest,
    MCPToolCallResult,
)

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RESOURCE_ID = re.compile(r"^[\w.:/()\-]{1,500}$")
_JURISDICTION = re.compile(r"^[\w .,'()\-]{1,200}$")
_ARTICLE = re.compile(r"^[\w.()\-\u00b7]{1,100}$")
_PROMPT_INJECTION = re.compile(
    r"(ignore (all |the )?(previous|system)|"
    r"\uc2dc\uc2a4\ud15c (\uaddc\uce59|\uc9c0\uce68).{0,20}(\ubb34\uc2dc|\uc6b0\ud68c)|"
    r"\ub2e4\ub978 (\uc694\uccad|tool).{0,20}(\ud638\ucd9c|\uc2e4\ud589)|call another tool)",
    re.IGNORECASE,
)
_COMMAND_INSTRUCTION = re.compile(
    r"(powershell|cmd\.exe|/bin/(?:sh|bash)|subprocess|execute command|"
    r"\uba85\ub839\uc5b4.{0,20}\uc2e4\ud589)",
    re.IGNORECASE,
)
_SCRIPT = re.compile(
    r"(<\s*script\b|on(?:load|error|click)\s*=|javascript\s*:)",
    re.IGNORECASE,
)
_CREDENTIAL = re.compile(
    r"(?:api[_ -]?key|password|access[_ -]?token|secret)\s*[:=]\s*"
    r"[A-Za-z0-9_\-/.+]{8,}|bearer\s+[A-Za-z0-9_\-/.+]{8,}",
    re.IGNORECASE,
)
_FORBIDDEN_ITEM_KEYS = frozenset(
    {
        "credential",
        "credential_reference",
        "token",
        "password",
        "api_key",
        "secret",
        "command",
        "server_name",
        "tool_name",
        "raw_response",
        "system_prompt",
        "hidden_reasoning",
    }
)
_INTERNAL_PATH = re.compile(
    r"(?:[A-Za-z]:\\(?:Users|Windows|ProgramData)\\|/(?:etc|home|root|var)/)",
    re.IGNORECASE,
)

_SEARCH_OPERATIONS = frozenset(
    {
        KoreanLawMcpOperation.SEARCH_LAWS,
        KoreanLawMcpOperation.SEARCH_CASES,
        KoreanLawMcpOperation.SEARCH_ADMINISTRATIVE_RULES,
        KoreanLawMcpOperation.SEARCH_LOCAL_ORDINANCES,
        KoreanLawMcpOperation.SEARCH_LEGAL_INTERPRETATIONS,
    }
)
_OPERATION_SOURCE_TYPES = {
    KoreanLawMcpOperation.SEARCH_LAWS: frozenset({"law"}),
    KoreanLawMcpOperation.GET_LEGAL_RESOURCE: KOREAN_LAW_SOURCE_TYPES,
    KoreanLawMcpOperation.SEARCH_CASES: frozenset({"case"}),
    KoreanLawMcpOperation.SEARCH_ADMINISTRATIVE_RULES: frozenset({"administrative_rule"}),
    KoreanLawMcpOperation.SEARCH_LOCAL_ORDINANCES: frozenset({"local_ordinance"}),
    KoreanLawMcpOperation.SEARCH_LEGAL_INTERPRETATIONS: frozenset({"legal_interpretation"}),
    KoreanLawMcpOperation.GET_ARTICLE_HISTORY: frozenset(
        {"law", "administrative_rule", "local_ordinance"}
    ),
    KoreanLawMcpOperation.COMPARE_VERSIONS: frozenset(
        {"law", "administrative_rule", "local_ordinance"}
    ),
    KoreanLawMcpOperation.EXPLORE_LEGAL_CHAIN: KOREAN_LAW_SOURCE_TYPES,
}


class KoreanLawMcpError(RuntimeError):
    code = "korean_law_mcp_error"
    retryable = False

    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class KoreanLawMcpInvalidRequestError(KoreanLawMcpError):
    code = "korean_law_invalid_request"


class KoreanLawMcpUnsupportedOperationError(KoreanLawMcpError):
    code = "korean_law_unsupported_operation"


class KoreanLawMcpToolUnavailableError(KoreanLawMcpError):
    code = "korean_law_tool_unavailable"


class KoreanLawMcpTimeoutError(KoreanLawMcpError):
    code = "korean_law_timeout"
    retryable = True


class KoreanLawMcpRateLimitError(KoreanLawMcpError):
    code = "korean_law_rate_limited"
    retryable = True


class KoreanLawMcpAuthenticationError(KoreanLawMcpError):
    code = "korean_law_authentication_failed"


class KoreanLawMcpUnavailableError(KoreanLawMcpError):
    code = "korean_law_unavailable"
    retryable = True


class KoreanLawMcpMalformedResponseError(KoreanLawMcpError):
    code = "korean_law_malformed_response"


class KoreanLawMcpResultTooLargeError(KoreanLawMcpError):
    code = "korean_law_result_too_large"


class KoreanLawMcpSecurityError(KoreanLawMcpError):
    code = "korean_law_security_violation"


class KoreanLawMcpResourceNotFoundError(KoreanLawMcpError):
    code = "korean_law_resource_not_found"


def _clean(value: str, field_name: str) -> str:
    cleaned = _CONTROL.sub("", value).replace("\r", " ").replace("\n", " ").strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


class KoreanLawMcpRequest(ProviderModel):
    operation: KoreanLawMcpOperation
    query: str | None = Field(default=None, max_length=8000)
    resource_id: str | None = Field(default=None, max_length=500)
    source_types: frozenset[str] = frozenset()
    jurisdiction: str | None = Field(default=None, max_length=200)
    effective_date: date | None = None
    date_from: date | None = None
    date_to: date | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    article_locator: str | None = Field(default=None, max_length=100)
    include_history: bool = False
    include_related: bool = False
    comparison_resource_ids: tuple[str, ...] = ()
    chain_depth: int = Field(default=1, ge=1, le=5)
    organization_id: UUID
    user_id: UUID
    request_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    classification: DataClassification = DataClassification.PUBLIC

    @field_validator("query")
    @classmethod
    def clean_query(cls, value):
        return _clean(value, "query") if value is not None else None

    @field_validator("resource_id")
    @classmethod
    def resource_format(cls, value):
        if value is None:
            return None
        value = _clean(value, "resource_id")
        if not _RESOURCE_ID.fullmatch(value):
            raise ValueError("Invalid resource_id")
        return value

    @field_validator("comparison_resource_ids")
    @classmethod
    def comparison_ids(cls, values):
        cleaned = tuple(_clean(value, "comparison_resource_id") for value in values)
        if any(not _RESOURCE_ID.fullmatch(value) for value in cleaned):
            raise ValueError("Invalid comparison resource identifier")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Comparison resource identifiers must be unique")
        return cleaned

    @field_validator("jurisdiction")
    @classmethod
    def jurisdiction_format(cls, value):
        if value is None:
            return None
        value = _clean(value, "jurisdiction")
        if not _JURISDICTION.fullmatch(value):
            raise ValueError("Invalid jurisdiction")
        return value

    @field_validator("article_locator")
    @classmethod
    def article_format(cls, value):
        if value is None:
            return None
        value = _clean(value, "article_locator")
        if not _ARTICLE.fullmatch(value):
            raise ValueError("Invalid article locator")
        return value

    @field_validator("correlation_id")
    @classmethod
    def correlation_format(cls, value):
        return _clean(value, "correlation_id")

    @model_validator(mode="after")
    def validate_operation(self):
        if self.operation in _SEARCH_OPERATIONS and not self.query:
            raise ValueError("Search operation requires query")
        if self.operation is KoreanLawMcpOperation.GET_LEGAL_RESOURCE and not self.resource_id:
            raise ValueError("Resource operation requires resource_id")
        if self.operation is KoreanLawMcpOperation.GET_ARTICLE_HISTORY and not (
            self.resource_id or self.article_locator
        ):
            raise ValueError("History operation requires resource_id or article_locator")
        if (
            self.operation is KoreanLawMcpOperation.COMPARE_VERSIONS
            and len(self.comparison_resource_ids) != 2
        ):
            raise ValueError("Compare operation requires exactly two resources")
        if self.operation is KoreanLawMcpOperation.EXPLORE_LEGAL_CHAIN and not (
            self.resource_id or self.query
        ):
            raise ValueError("Chain operation requires resource_id or query")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Invalid date range")
        supported = _OPERATION_SOURCE_TYPES[self.operation]
        if self.source_types and not self.source_types <= supported:
            raise ValueError("Source type is incompatible with operation")
        return self


class KoreanLawSearchRequest(KoreanLawMcpRequest):
    operation: Literal[
        KoreanLawMcpOperation.SEARCH_LAWS,
        KoreanLawMcpOperation.SEARCH_CASES,
        KoreanLawMcpOperation.SEARCH_ADMINISTRATIVE_RULES,
        KoreanLawMcpOperation.SEARCH_LOCAL_ORDINANCES,
        KoreanLawMcpOperation.SEARCH_LEGAL_INTERPRETATIONS,
    ] = KoreanLawMcpOperation.SEARCH_LAWS
    query: str = Field(min_length=1, max_length=8000)
    source_types: frozenset[str] = frozenset({"law"})


class KoreanLawResourceRequest(KoreanLawMcpRequest):
    operation: Literal[KoreanLawMcpOperation.GET_LEGAL_RESOURCE] = (
        KoreanLawMcpOperation.GET_LEGAL_RESOURCE
    )
    resource_id: str = Field(min_length=1, max_length=500)


class KoreanLawHistoryRequest(KoreanLawMcpRequest):
    operation: Literal[KoreanLawMcpOperation.GET_ARTICLE_HISTORY] = (
        KoreanLawMcpOperation.GET_ARTICLE_HISTORY
    )


class KoreanLawCompareRequest(KoreanLawMcpRequest):
    operation: Literal[KoreanLawMcpOperation.COMPARE_VERSIONS] = (
        KoreanLawMcpOperation.COMPARE_VERSIONS
    )


class KoreanLawChainRequest(KoreanLawMcpRequest):
    operation: Literal[KoreanLawMcpOperation.EXPLORE_LEGAL_CHAIN] = (
        KoreanLawMcpOperation.EXPLORE_LEGAL_CHAIN
    )


class KoreanLawMcpRequestBuilder:
    def __init__(
        self,
        registry: KoreanLawMcpToolRegistry,
        *,
        discovered_tool_names: frozenset[str] | None = None,
        server_name: str = KOREAN_LAW_PROVIDER_NAME,
    ) -> None:
        self.registry = registry
        self.discovered_tool_names = discovered_tool_names
        self.server_name = server_name
        self.resolver = KoreanLawMcpCapabilityResolver(registry)

    def build(
        self, request: KoreanLawMcpRequest, context: MCPExecutionContext
    ) -> MCPToolCallRequest:
        if (
            request.organization_id != context.organization_id
            or request.user_id != context.user_id
            or request.request_id != context.request_id
            or request.correlation_id != context.correlation_id
        ):
            raise KoreanLawMcpInvalidRequestError("Request context mismatch")
        try:
            mapping = (
                self.resolver.require_available(request.operation, self.discovered_tool_names)
                if self.discovered_tool_names is not None
                else self.registry.get(request.operation)
            )
        except KoreanLawMcpToolNotFoundError as exc:
            raise KoreanLawMcpUnsupportedOperationError(
                "Korean Law operation is unsupported"
            ) from exc
        except KoreanLawMcpCapabilityMismatchError as exc:
            raise KoreanLawMcpToolUnavailableError("Korean Law MCP tool is unavailable") from exc
        arguments = self._arguments(request)
        return MCPToolCallRequest(
            server_name=self.server_name,
            tool_name=mapping.configured_tool_name,
            arguments=arguments,
            context=context,
        )

    @staticmethod
    def _arguments(request: KoreanLawMcpRequest) -> dict[str, object]:
        ordered = (
            ("query", request.query),
            ("resource_id", request.resource_id),
            ("source_types", sorted(request.source_types) if request.source_types else None),
            ("jurisdiction", request.jurisdiction),
            (
                "effective_date",
                request.effective_date.isoformat() if request.effective_date else None,
            ),
            ("date_from", request.date_from.isoformat() if request.date_from else None),
            ("date_to", request.date_to.isoformat() if request.date_to else None),
            ("top_k", request.top_k),
            ("article_locator", request.article_locator),
            ("include_history", request.include_history or None),
            ("include_related", request.include_related or None),
            (
                "comparison_resource_ids",
                list(request.comparison_resource_ids) if request.comparison_resource_ids else None,
            ),
            (
                "chain_depth",
                request.chain_depth
                if request.operation is KoreanLawMcpOperation.EXPLORE_LEGAL_CHAIN
                else None,
            ),
        )
        return {key: value for key, value in ordered if value is not None}


class KoreanLawMcpRawResponse(ProviderModel):
    operation: KoreanLawMcpOperation
    items: tuple[dict[str, Any], ...]
    total_count: int = Field(ge=0)
    result_size: int = Field(ge=0)
    warnings: tuple[str, ...] = ()
    empty: bool = False


def _depth(value: Any, current: int = 0) -> int:
    if current > 5:
        raise KoreanLawMcpMalformedResponseError("MCP response nesting exceeds limit")
    if isinstance(value, dict):
        for nested in value.values():
            _depth(nested, current + 1)
    elif isinstance(value, list):
        for nested in value:
            _depth(nested, current + 1)
    return current


class KoreanLawMcpResponseValidator:
    def __init__(
        self,
        registry: KoreanLawMcpToolRegistry,
        *,
        max_items: int = 100,
        max_response_bytes: int = 1_000_000,
        max_string_length: int = 50_000,
    ) -> None:
        self.registry = registry
        self.max_items = max_items
        self.max_response_bytes = max_response_bytes
        self.max_string_length = max_string_length

    def validate(
        self,
        operation: KoreanLawMcpOperation,
        result: MCPToolCallResult,
    ) -> KoreanLawMcpRawResponse:
        if "json" not in result.content_type.casefold():
            raise KoreanLawMcpMalformedResponseError("MCP response must be JSON")
        try:
            encoded = json.dumps(result.content, ensure_ascii=False, default=str).encode()
        except (TypeError, ValueError) as exc:
            raise KoreanLawMcpMalformedResponseError("MCP response is not serializable") from exc
        response_size = max(result.result_size, len(encoded))
        if response_size > self.max_response_bytes:
            raise KoreanLawMcpResultTooLargeError("MCP response exceeds size limit")
        _depth(result.content)
        items = self._items(result.content)
        if len(items) > self.max_items:
            raise KoreanLawMcpResultTooLargeError("MCP response has too many items")
        mapping = self.registry.get(operation)
        seen = set()
        sanitized = []
        warnings = list(result.warnings)
        for item in items:
            normalized, item_warnings = self._validate_item(item, mapping)
            identifier = normalized["resource_id"]
            if identifier in seen:
                raise KoreanLawMcpMalformedResponseError(
                    "MCP response contains duplicate resources"
                )
            seen.add(identifier)
            sanitized.append(normalized)
            warnings.extend(item_warnings)
        return KoreanLawMcpRawResponse(
            operation=operation,
            items=tuple(sanitized),
            total_count=len(sanitized),
            result_size=response_size,
            warnings=tuple(dict.fromkeys(warnings)),
            empty=not sanitized,
        )

    @staticmethod
    def _items(content: object) -> list[dict[str, Any]]:
        if not isinstance(content, dict):
            raise KoreanLawMcpMalformedResponseError("MCP response schema is invalid")
        if "items" in content:
            values = content["items"]
        elif "result" in content:
            values = [content["result"]] if content["result"] is not None else []
        elif "content" in content:
            values = content["content"]
            values = values if isinstance(values, list) else [values]
        else:
            raise KoreanLawMcpMalformedResponseError("MCP response has no result field")
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise KoreanLawMcpMalformedResponseError("MCP response items are invalid")
        return values

    def _validate_item(self, item, mapping):
        resource_id = item.get("resource_id") or item.get("source_id")
        if not isinstance(resource_id, str) or not _RESOURCE_ID.fullmatch(resource_id):
            raise KoreanLawMcpMalformedResponseError("Resource identifier is missing or invalid")
        source_type = item.get("source_type")
        if (
            source_type not in KOREAN_LAW_SOURCE_TYPES
            or source_type not in mapping.supported_source_types
        ):
            raise KoreanLawMcpMalformedResponseError("Unsupported source type")
        warnings = []
        normalized = {}
        for key, value in item.items():
            if key.casefold() in _FORBIDDEN_ITEM_KEYS:
                raise KoreanLawMcpSecurityError("Sensitive provider field was blocked")
            if isinstance(value, str):
                if len(value) > self.max_string_length:
                    raise KoreanLawMcpResultTooLargeError("MCP response string is too large")
                self._security(value)
                if _PROMPT_INJECTION.search(value):
                    warnings.append("prompt_injection_treated_as_data")
                if _COMMAND_INSTRUCTION.search(value):
                    warnings.append("executable_instruction_treated_as_data")
            if key.endswith("_date") and value is not None:
                try:
                    date.fromisoformat(str(value))
                except ValueError as exc:
                    raise KoreanLawMcpMalformedResponseError(
                        "MCP response contains invalid date"
                    ) from exc
            if key.endswith("_url") and value is not None:
                self._validate_url(str(value))
            if key == "metadata":
                if not isinstance(value, dict):
                    raise KoreanLawMcpMalformedResponseError("Metadata must be an object")
                if not set(value) <= mapping.metadata_allowlist:
                    raise KoreanLawMcpMalformedResponseError(
                        "Metadata contains non-allowlisted keys"
                    )
            normalized[key] = value
        normalized["resource_id"] = resource_id
        return normalized, warnings

    @staticmethod
    def _security(value: str) -> None:
        if _SCRIPT.search(value):
            raise KoreanLawMcpSecurityError("Executable markup was blocked")
        if _CREDENTIAL.search(value):
            raise KoreanLawMcpSecurityError("Credential-like content was blocked")
        if _INTERNAL_PATH.search(value):
            raise KoreanLawMcpSecurityError("Internal path disclosure was blocked")

    @staticmethod
    def _validate_url(value: str) -> None:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise KoreanLawMcpSecurityError("Unsafe source URL was blocked")
        host = parsed.hostname.casefold()
        if host == "localhost" or host.endswith(".local"):
            raise KoreanLawMcpSecurityError("Private source endpoint was blocked")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return
        if not address.is_global:
            raise KoreanLawMcpSecurityError("Private source endpoint was blocked")


class FakeKoreanLawMcpGateway:
    """Deterministic gateway double with no network or process behavior."""

    def __init__(
        self,
        results: dict[str, MCPToolCallResult] | None = None,
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.results = results or {}
        self.errors = errors or {}
        self.calls: list[MCPToolCallRequest] = []

    async def call_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult:
        self.calls.append(request)
        if request.tool_name in self.errors:
            raise self.errors[request.tool_name]
        try:
            return self.results[request.tool_name]
        except KeyError as exc:
            raise MCPError(MCPErrorCode.UNKNOWN_TOOL, "Fake MCP tool is unavailable") from exc


class KoreanLawMcpClientAdapter:
    def __init__(
        self,
        gateway,
        builder: KoreanLawMcpRequestBuilder,
        validator: KoreanLawMcpResponseValidator,
    ) -> None:
        self.gateway = gateway
        self.builder = builder
        self.validator = validator

    async def execute(
        self, request: KoreanLawMcpRequest, context: MCPExecutionContext
    ) -> KoreanLawMcpRawResponse:
        tool_call = self.builder.build(request, context)
        try:
            result = await self.gateway.call_tool(tool_call)
        except TimeoutError as exc:
            raise KoreanLawMcpTimeoutError("Korean Law MCP request timed out") from exc
        except MCPError as exc:
            raise self._map_error(exc) from exc
        return self.validator.validate(request.operation, result)

    @staticmethod
    def _map_error(error: MCPError) -> KoreanLawMcpError:
        mapping = {
            MCPErrorCode.TIMEOUT: KoreanLawMcpTimeoutError,
            MCPErrorCode.RATE_LIMIT: KoreanLawMcpRateLimitError,
            MCPErrorCode.AUTHENTICATION: KoreanLawMcpAuthenticationError,
            MCPErrorCode.CONNECTION: KoreanLawMcpUnavailableError,
            MCPErrorCode.DISABLED: KoreanLawMcpToolUnavailableError,
            MCPErrorCode.UNKNOWN_TOOL: KoreanLawMcpToolUnavailableError,
            MCPErrorCode.RESULT: KoreanLawMcpMalformedResponseError,
            MCPErrorCode.RESULT_TOO_LARGE: KoreanLawMcpResultTooLargeError,
            MCPErrorCode.PERMISSION: KoreanLawMcpSecurityError,
            MCPErrorCode.POLICY: KoreanLawMcpSecurityError,
            MCPErrorCode.APPROVAL: KoreanLawMcpSecurityError,
            MCPErrorCode.VALIDATION: KoreanLawMcpInvalidRequestError,
        }
        error_type = mapping.get(error.code, KoreanLawMcpUnavailableError)
        return error_type("Korean Law MCP request failed")
