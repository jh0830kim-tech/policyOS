"""Connector response parser implementations with content-type validation."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from app.connectors.domain import ConnectorError, ConnectorSchemaError


@dataclass(frozen=True)
class ParsedConnectorItem:
    title: str | None = None
    text: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ParsedConnectorResponse:
    items: list[ParsedConnectorItem]
    pagination: dict[str, Any] | None = None
    freshness: dict[str, Any] | None = None


@dataclass(frozen=True)
class PaginationMetadata:
    page: int | None = None
    offset: int | None = None
    cursor: str | None = None
    next_url: str | None = None


@dataclass(frozen=True)
class SourceFreshnessMetadata:
    source_version: str | None = None
    effective_date: str | None = None


class JsonConnectorResponseParser:
    def parse(self, payload: bytes, *, content_type: str | None = None) -> ParsedConnectorResponse:
        if content_type and "json" not in content_type.lower():
            raise ConnectorSchemaError("JSON parser expected application/json")
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorSchemaError("Malformed JSON connector response") from exc
        items = []
        for item in data.get("items", []):
            items.append(ParsedConnectorItem(title=item.get("title"), metadata=dict(item)))
        return ParsedConnectorResponse(
            items=items, pagination=data.get("pagination"), freshness=data.get("freshness")
        )


class XmlConnectorResponseParser:
    def parse(self, payload: bytes, *, content_type: str | None = None) -> ParsedConnectorResponse:
        if content_type and "xml" not in content_type.lower():
            raise ConnectorSchemaError("XML parser expected application/xml")
        if b"<!DOCTYPE" in payload.upper():
            raise ConnectorError("Unsafe XML response", code="connector_schema_error")
        try:
            root = ET.fromstring(payload.decode("utf-8"))
        except (UnicodeDecodeError, ET.ParseError) as exc:
            raise ConnectorSchemaError("Malformed XML connector response") from exc
        items = []
        for item in root.findall(".//item"):
            title = item.findtext("title")
            items.append(
                ParsedConnectorItem(title=title, metadata={child.tag: child.text for child in item})
            )
        return ParsedConnectorResponse(items=items)


class TextConnectorResponseParser:
    def parse(self, payload: bytes, *, content_type: str | None = None) -> ParsedConnectorResponse:
        if (
            content_type
            and "text" not in content_type.lower()
            and "plain" not in content_type.lower()
        ):
            raise ConnectorSchemaError("Text parser expected text/plain")
        text = payload.decode("utf-8", errors="ignore")
        return ParsedConnectorResponse(items=[ParsedConnectorItem(text=text)])
