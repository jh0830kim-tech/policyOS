from app.knowledge.schemas import ParsedDocument, UnsupportedDocumentTypeError


class HwpDocumentParser:
    name = "unsupported-hwp-adapter"
    version = "1.0.0"
    extensions = frozenset({".hwp", ".hwpx"})
    mime_types = frozenset(
        {
            "application/x-hwp",
            "application/haansofthwp",
            "application/vnd.hancom.hwpx",
        }
    )

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        raise UnsupportedDocumentTypeError("HWP and HWPX parsing is not configured")