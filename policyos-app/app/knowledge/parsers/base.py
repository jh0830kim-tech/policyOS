"""Parser contracts and registry."""

from typing import Protocol

from app.knowledge.schemas import ParsedDocument, UnsupportedDocumentTypeError


class DocumentParser(Protocol):
    name: str
    version: str
    extensions: frozenset[str]
    mime_types: frozenset[str]

    def parse(self, content: bytes, filename: str) -> ParsedDocument: ...


class ParserRegistry:
    def __init__(self, parsers: list[DocumentParser]) -> None:
        self._parsers = parsers

    def get(self, extension: str, mime_type: str) -> DocumentParser:
        matches = [parser for parser in self._parsers if extension in parser.extensions]
        if not matches:
            raise UnsupportedDocumentTypeError("Document type is not supported")
        parser = matches[0]
        if mime_type not in parser.mime_types:
            raise UnsupportedDocumentTypeError("Declared MIME type does not match document type")
        return parser