import csv
from io import StringIO

from app.knowledge.schemas import ParsedDocument, ParsedSection, ParserError


class CsvDocumentParser:
    name = "stdlib-csv"
    version = "1.0.0"
    extensions = frozenset({".csv"})
    mime_types = frozenset({"text/csv", "application/csv", "application/vnd.ms-excel"})

    def __init__(self, *, max_rows: int = 10_000, max_columns: int = 200) -> None:
        self.max_rows = max_rows
        self.max_columns = max_columns

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        try:
            decoded = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise ParserError("CSV document must use UTF-8 encoding") from exc
        try:
            dialect = csv.Sniffer().sniff(decoded[:8_192], delimiters=",;\t|")
            rows = list(csv.reader(StringIO(decoded), dialect))
        except csv.Error as exc:
            raise ParserError("CSV document could not be parsed") from exc
        if not rows or not any(any(cell.strip() for cell in row) for row in rows):
            raise ParserError("CSV document contains no data")
        if len(rows) > self.max_rows:
            raise ParserError("CSV row limit exceeded")
        if max((len(row) for row in rows), default=0) > self.max_columns:
            raise ParserError("CSV column limit exceeded")
        header = rows[0]
        rendered = [" | ".join(row) for row in rows]
        return ParsedDocument(
            text="\n".join(rendered),
            sections=[
                ParsedSection(
                    index=1,
                    kind="table",
                    text="\n".join(rendered),
                    start_row=1,
                    end_row=len(rows),
                    metadata={"header": header, "row_count": len(rows)},
                )
            ],
            parser_name=self.name,
            parser_version=self.version,
            metadata={"header": header, "row_count": len(rows), "column_count": len(header)},
        )