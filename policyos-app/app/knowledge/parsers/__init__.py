from app.knowledge.parsers.base import DocumentParser, ParserRegistry
from app.knowledge.parsers.csv import CsvDocumentParser
from app.knowledge.parsers.docx import DocxDocumentParser
from app.knowledge.parsers.hwp import HwpDocumentParser
from app.knowledge.parsers.pdf import PdfDocumentParser
from app.knowledge.parsers.text import TextDocumentParser
from app.knowledge.parsers.xlsx import XlsxDocumentParser


def default_parser_registry() -> ParserRegistry:
    return ParserRegistry(
        [
            TextDocumentParser(),
            PdfDocumentParser(),
            DocxDocumentParser(),
            CsvDocumentParser(),
            XlsxDocumentParser(),
            HwpDocumentParser(),
        ]
    )


__all__ = [
    "CsvDocumentParser",
    "DocumentParser",
    "DocxDocumentParser",
    "HwpDocumentParser",
    "ParserRegistry",
    "PdfDocumentParser",
    "TextDocumentParser",
    "XlsxDocumentParser",
    "default_parser_registry",
]