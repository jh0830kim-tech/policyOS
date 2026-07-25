"""Pagination strategies for connector search requests."""

from __future__ import annotations

from app.connectors.domain import ConnectorError


class PaginationStrategy:
    def next_page(self, page_cursor: object, current_page: int, records_seen: int) -> object | None:
        raise NotImplementedError


class PageNumberPagination(PaginationStrategy):
    def __init__(self, *, max_pages: int = 10, max_records: int = 1000) -> None:
        self.max_pages = max_pages
        self.max_records = max_records

    def next_page(self, page_cursor: object, current_page: int, records_seen: int) -> int | None:
        if records_seen >= self.max_records:
            return None
        if int(page_cursor) >= self.max_pages:
            return None
        return int(page_cursor) + 1


class OffsetPagination(PaginationStrategy):
    def __init__(self, *, limit: int = 100, max_pages: int = 10, max_records: int = 1000) -> None:
        if limit <= 0:
            raise ValueError("Pagination limit must be positive")
        self.limit = limit
        self.max_pages = max_pages
        self.max_records = max_records

    def next_page(self, page_cursor: object, current_page: int, records_seen: int) -> int | None:
        if records_seen >= self.max_records or current_page >= self.max_pages:
            return None
        return int(page_cursor) + self.limit


class CursorPagination(PaginationStrategy):
    def __init__(self, *, max_pages: int = 10, max_records: int = 1000) -> None:
        self.max_pages = max_pages
        self.max_records = max_records
        self._seen: set[str] = set()

    def next_page(self, page_cursor: object, current_page: int, records_seen: int) -> str | None:
        if records_seen >= self.max_records:
            return None
        value = str(page_cursor)
        if current_page >= self.max_pages:
            return None
        if page_cursor is None or str(page_cursor) == "":
            return None
        if value in self._seen:
            raise ConnectorError("Repeated connector cursor detected", code="connector_cursor_loop")
        self._seen.add(value)
        return value
