"""Bounded JSON input/output validation for untrusted MCP data."""

import json
import re
from urllib.parse import urlparse

from app.mcp.domain import MCPError, MCPErrorCode, MCPToolCallResult, MCPToolDefinition

_DANGEROUS = re.compile(r"(?:\.\.[\\/]|[;&|`]\s*(?:rm|del|curl|wget|powershell|cmd)\b)", re.I)
_INJECTION = re.compile(
    r"(?:ignore (?:all|previous) instructions|system prompt|<script\b|javascript:)", re.I
)


def _validate(schema: dict[str, object], value: object, path: str = "$") -> None:
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            raise MCPError(MCPErrorCode.VALIDATION, f"{path} must be an object")
        required = schema.get("required", [])
        for name in required:
            if name not in value:
                raise MCPError(MCPErrorCode.VALIDATION, f"Missing required field: {name}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and any(key not in props for key in value):
            raise MCPError(MCPErrorCode.VALIDATION, "Unknown input field")
        if len(value) > 100:
            raise MCPError(MCPErrorCode.VALIDATION, "Object is too large")
        for key, item in value.items():
            if key in props:
                _validate(props[key], item, f"{path}.{key}")
    elif kind == "array":
        if not isinstance(value, list) or len(value) > 1000:
            raise MCPError(MCPErrorCode.VALIDATION, f"{path} must be a bounded array")
        for item in value:
            _validate(schema.get("items", {}), item, path)
    elif kind == "string":
        if not isinstance(value, str) or len(value) > int(schema.get("maxLength", 8000)):
            raise MCPError(MCPErrorCode.VALIDATION, f"{path} is invalid")
        if _DANGEROUS.search(value):
            raise MCPError(MCPErrorCode.VALIDATION, "Unsafe path or command input")
        if schema.get("format") == "uri" and urlparse(value).scheme not in {"https", "http"}:
            raise MCPError(MCPErrorCode.VALIDATION, "Unsafe URL")


def validate_input(tool: MCPToolDefinition, arguments: dict[str, object]) -> None:
    _validate(tool.input_schema, arguments)


def validate_output(
    tool: MCPToolDefinition, result: MCPToolCallResult, max_bytes: int
) -> MCPToolCallResult:
    encoded = json.dumps(result.content, ensure_ascii=False, default=str).encode()
    if len(encoded) > max_bytes:
        raise MCPError(MCPErrorCode.RESULT_TOO_LARGE, "MCP result exceeds size limit")
    _validate(tool.output_schema, result.content)
    text = encoded.decode(errors="replace")
    warnings = list(result.warnings)
    suspicious = False
    if _INJECTION.search(text):
        warnings.append("suspicious_untrusted_content")
        suspicious = True
    return result.model_copy(
        update={
            "result_size": len(encoded),
            "warnings": tuple(dict.fromkeys(warnings)),
            "suspicious": suspicious,
            "untrusted": True,
        }
    )
