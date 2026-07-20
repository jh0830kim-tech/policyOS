from io import BytesIO

import pypdf
from pypdf import PdfReader

from app.knowledge.schemas import ParsedDocument, ParsedSection, ParserError


class PdfDocumentParser:
    name = "pypdf"
    version = pypdf.__version__
    extensions = frozenset({".pdf"})
    mime_types = frozenset({"application/pdf"})

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise ParserError("Encrypted PDF documents are not supported")
            sections = [
                ParsedSection(
                    index=index,
                    kind="page",
                    page_number=index,
                    title=f"Page {index}",
                    text=page.extract_text() or "",
                )
                for index, page in enumerate(reader.pages, start=1)
            ]
        except ParserError:
            raise
        except Exception as exc:
            raise ParserError("PDF document could not be parsed") from exc
        if not any(section.text.strip() for section in sections):
            raise ParserError("PDF contains no extractable text; OCR is not automatic")
        return ParsedDocument(
            text="\n\n".join(section.text for section in sections if section.text.strip()),
            sections=sections,
            parser_name=self.name,
            parser_version=self.version,
            page_count=len(sections),
        )