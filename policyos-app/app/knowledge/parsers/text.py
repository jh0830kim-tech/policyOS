from app.knowledge.schemas import ParsedDocument, ParsedSection, ParserError


class TextDocumentParser:
    name = "text"
    version = "1.0.0"
    extensions = frozenset({".txt", ".md"})
    mime_types = frozenset({"text/plain", "text/markdown", "text/x-markdown"})

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            decoded = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise ParserError("Text document must use UTF-8 encoding") from exc
        if not decoded.strip():
            raise ParserError("Document contains no text")
        sections: list[ParsedSection] = []
        if filename.lower().endswith(".md"):
            current_title: str | None = None
            current: list[str] = []
            for line in decoded.splitlines():
                if line.lstrip().startswith("#"):
                    if current or current_title:
                        sections.append(
                            ParsedSection(
                                index=len(sections) + 1,
                                title=current_title,
                                text="\n".join(current),
                            )
                        )
                    current_title = line.lstrip("#").strip() or None
                    current = []
                else:
                    current.append(line)
            if current or current_title:
                sections.append(
                    ParsedSection(
                        index=len(sections) + 1,
                        title=current_title,
                        text="\n".join(current),
                    )
                )
        if not sections:
            sections = [ParsedSection(index=1, text=decoded)]
        return ParsedDocument(
            text=decoded,
            sections=sections,
            parser_name=self.name,
            parser_version=self.version,
        )