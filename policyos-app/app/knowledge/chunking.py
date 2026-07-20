"""Deterministic, structure-aware knowledge chunking."""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.privacy import DataClassification
from app.knowledge.schemas import ParsedDocument, ParsedSection


class ChunkingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChunkingConfig(ChunkingModel):
    max_characters: int = Field(default=4_000, ge=100, le=100_000)
    target_characters: int = Field(default=3_000, ge=50, le=100_000)
    overlap_characters: int = Field(default=300, ge=0, le=20_000)
    min_characters: int = Field(default=200, ge=1, le=20_000)
    preserve_page_boundaries: bool = True
    preserve_section_boundaries: bool = True
    preserve_tables: bool = True
    preserve_lists: bool = True
    normalization_version: str = Field(default="1.0.0", min_length=1, max_length=50)
    chunking_strategy_version: str = Field(default="1.0.0", min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_sizes(self) -> Self:
        if self.target_characters > self.max_characters:
            raise ValueError("target_characters cannot exceed max_characters")
        if self.min_characters > self.target_characters:
            raise ValueError("min_characters cannot exceed target_characters")
        if self.overlap_characters >= self.max_characters:
            raise ValueError("overlap_characters must be smaller than max_characters")
        return self

    @property
    def config_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class CitationLocator(ChunkingModel):
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_path: str | None = Field(default=None, max_length=1_000)
    heading: str | None = Field(default=None, max_length=500)
    source_locator: str | None = Field(default=None, max_length=1_000)


class ChunkMetadata(ChunkingModel):
    document_version_id: uuid.UUID
    chunk_index: int = Field(ge=0)
    locator: CitationLocator
    source_block_start: int = Field(ge=0)
    source_block_end: int = Field(ge=0)
    token_estimate: int = Field(ge=0)
    character_count: int = Field(ge=0)
    content_hash: str = Field(min_length=64, max_length=64)
    chunking_config_hash: str = Field(min_length=64, max_length=64)
    chunking_strategy_version: str
    normalization_version: str
    data_classification: DataClassification
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ChunkCandidate(ChunkingModel):
    content: str
    metadata: ChunkMetadata


class ChunkingRequest(ChunkingModel):
    organization_id: uuid.UUID
    document_version_id: uuid.UUID
    data_classification: DataClassification
    parsed_document: ParsedDocument
    config: ChunkingConfig = Field(default_factory=ChunkingConfig)


class ChunkingResult(ChunkingModel):
    document_version_id: uuid.UUID
    config_hash: str
    strategy_version: str
    chunks: list[ChunkCandidate]
    idempotent: bool = False


class ChunkingError(ValueError):
    pass


class TokenEstimator(Protocol):
    def estimate(self, text: str) -> int: ...


class SimpleTokenEstimator:
    """Stable heuristic only; never use this value for provider billing."""

    def estimate(self, text: str) -> int:
        return 0 if not text else max(1, (len(text) + 3) // 4)


class FakeTokenEstimator:
    def __init__(self, value: int = 7) -> None:
        self.value = value
        self.calls: list[str] = []

    def estimate(self, text: str) -> int:
        self.calls.append(text)
        return self.value


@dataclass
class _Block:
    text: str
    source_start: int
    source_end: int
    page: int | None
    section_path: str | None
    heading: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def boundary(self) -> tuple[int | None, str | None, str | None]:
        return self.page, self.section_path, self.heading


class DeterministicChunker:
    def __init__(self, estimator: TokenEstimator | None = None) -> None:
        self.estimator = estimator or SimpleTokenEstimator()

    def chunk(self, request: ChunkingRequest) -> ChunkingResult:
        blocks = self._blocks(request.parsed_document.sections, request.config)
        if not blocks:
            raise ChunkingError("Document contains no chunkable content")
        groups = self._group(blocks, request.config)
        chunks = [self._candidate(group, index, request) for index, group in enumerate(groups)]
        chunks = self._merge_small_tail(chunks, request)
        unique: list[ChunkCandidate] = []
        seen: set[tuple[str, int, int, str | None]] = set()
        for chunk in chunks:
            key = (
                chunk.metadata.content_hash,
                chunk.metadata.source_block_start,
                chunk.metadata.source_block_end,
                chunk.metadata.locator.source_locator,
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(chunk)
        return ChunkingResult(
            document_version_id=request.document_version_id,
            config_hash=request.config.config_hash,
            strategy_version=request.config.chunking_strategy_version,
            chunks=[
                item.model_copy(
                    update={"metadata": item.metadata.model_copy(update={"chunk_index": i})}
                )
                for i, item in enumerate(unique)
            ],
        )

    def _blocks(self, sections: list[ParsedSection], config: ChunkingConfig) -> list[_Block]:
        blocks: list[_Block] = []
        source_index = 0
        for section in sections:
            path = self._section_path(section)
            if section.kind in {"table", "sheet"} and config.preserve_tables:
                table_blocks = self._table_blocks(section, path, source_index, config)
                blocks.extend(table_blocks)
                source_index = (
                    max((item.source_end for item in table_blocks), default=source_index) + 1
                )
                continue
            paragraphs = [
                item.strip() for item in re.split(r"\n\s*\n", section.text) if item.strip()
            ]
            for paragraph in paragraphs:
                if config.preserve_lists and self._is_list(paragraph):
                    list_blocks = self._list_blocks(section, paragraph, path, source_index, config)
                    blocks.extend(list_blocks)
                    source_index = (
                        max((item.source_end for item in list_blocks), default=source_index) + 1
                    )
                    continue
                pieces = self._safe_split(paragraph, config.max_characters)
                blocks.extend(
                    _Block(
                        text=piece,
                        source_start=source_index,
                        source_end=source_index,
                        page=section.page_number,
                        section_path=path,
                        heading=section.title,
                        metadata={"block_type": "paragraph"},
                    )
                    for piece in pieces
                )
                source_index += 1
        return blocks

    def _table_blocks(
        self, section: ParsedSection, path: str | None, start: int, config: ChunkingConfig
    ) -> list[_Block]:
        rows = [row for row in section.text.splitlines() if row.strip()]
        headers = section.metadata.get("header")
        header = " | ".join(str(item) for item in headers) if isinstance(headers, list) else None
        if header and rows and rows[0].strip() == header.strip():
            rows = rows[1:]
        if not rows and header:
            rows = [header]
        groups: list[tuple[list[str], int, int]] = []
        current: list[str] = []
        row_start = 1
        for offset, row in enumerate(rows, start=1):
            prefix = [header] if header else []
            candidate = "\n".join([*prefix, *current, row])
            if current and len(candidate) > config.max_characters:
                groups.append((current, row_start, offset - 1))
                current = []
                row_start = offset
            if len(row) + (len(header) + 1 if header else 0) > config.max_characters:
                for piece in self._safe_split(row, config.max_characters - (len(header or "") + 1)):
                    groups.append(([piece], offset, offset))
                continue
            current.append(row)
        if current:
            groups.append((current, row_start, row_start + len(current) - 1))
        result = []
        for group_index, (group, row_start, row_end) in enumerate(groups):
            text = "\n".join(([header] if header else []) + group)
            result.append(
                _Block(
                    text=text,
                    source_start=start + row_start - 1,
                    source_end=start + row_end - 1,
                    page=section.page_number,
                    section_path=path,
                    heading=section.title,
                    metadata={
                        "block_type": "table",
                        "table_index": section.index,
                        "sheet_name": section.sheet_name,
                        "row_start": section.start_row or row_start,
                        "row_end": (section.start_row or 1) + row_end - 1,
                        "column_headers": headers or [],
                        "table_part": group_index,
                    },
                )
            )
        return result

    def _list_blocks(
        self,
        section: ParsedSection,
        paragraph: str,
        path: str | None,
        start: int,
        config: ChunkingConfig,
    ) -> list[_Block]:
        items = [line.strip() for line in paragraph.splitlines() if line.strip()]
        numbered = bool(items and re.match(r"^\d+[.)]\s+", items[0]))
        result: list[_Block] = []
        current: list[str] = []
        item_start = 1
        for offset, item in enumerate(items, start=1):
            if current and len("\n".join([*current, item])) > config.max_characters:
                result.append(
                    self._list_block(
                        current, section, path, start, item_start, offset - 1, numbered
                    )
                )
                current = []
                item_start = offset
            current.extend(self._safe_split(item, config.max_characters))
        if current:
            result.append(
                self._list_block(current, section, path, start, item_start, len(items), numbered)
            )
        return result

    @staticmethod
    def _list_block(
        items: list[str],
        section: ParsedSection,
        path: str | None,
        start: int,
        item_start: int,
        item_end: int,
        numbered: bool,
    ) -> _Block:
        return _Block(
            text="\n".join(items),
            source_start=start + item_start - 1,
            source_end=start + item_end - 1,
            page=section.page_number,
            section_path=path,
            heading=section.title,
            metadata={
                "block_type": "list",
                "list_type": "numbered" if numbered else "bullet",
                "item_start": item_start,
                "item_end": item_end,
                "parent_heading": section.title,
                "numbering_preserved": True,
            },
        )

    def _group(self, blocks: list[_Block], config: ChunkingConfig) -> list[list[_Block]]:
        groups: list[list[_Block]] = []
        current: list[_Block] = []
        for block in blocks:
            boundary_changed = bool(
                current
                and (
                    config.preserve_page_boundaries
                    and current[-1].page != block.page
                    or config.preserve_section_boundaries
                    and current[-1].boundary[1:] != block.boundary[1:]
                )
            )
            candidate_size = len(self._join([*current, block]))
            if current and (
                boundary_changed
                or candidate_size > config.max_characters
                or len(self._join(current)) >= config.target_characters
            ):
                groups.append(current)
                current = self._overlap_tail(current, config.overlap_characters)
                if boundary_changed:
                    current = []
            if len(block.text) > config.max_characters:
                raise ChunkingError("Internal block exceeded maximum chunk size")
            if current and len(self._join([*current, block])) > config.max_characters:
                groups.append(current)
                current = []
            current.append(block)
        if current:
            groups.append(current)
        return groups

    def _candidate(
        self, blocks: list[_Block], chunk_index: int, request: ChunkingRequest
    ) -> ChunkCandidate:
        content = self._join(blocks)
        pages = [item.page for item in blocks if item.page is not None]
        paths = [item.section_path for item in blocks if item.section_path]
        headings = [item.heading for item in blocks if item.heading]
        page_start, page_end = (min(pages), max(pages)) if pages else (None, None)
        section_path = paths[0] if paths and len(set(paths)) == 1 else None
        heading = headings[0] if headings and len(set(headings)) == 1 else None
        locator_parts = []
        if page_start is not None:
            locator_parts.append(
                f"p. {page_start}" if page_start == page_end else f"pp. {page_start}-{page_end}"
            )
        if section_path:
            locator_parts.append(section_path)
        metadata = self._merge_metadata(blocks)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return ChunkCandidate(
            content=content,
            metadata=ChunkMetadata(
                document_version_id=request.document_version_id,
                chunk_index=chunk_index,
                locator=CitationLocator(
                    page_start=page_start,
                    page_end=page_end,
                    section_path=section_path,
                    heading=heading,
                    source_locator=" / ".join(locator_parts) or None,
                ),
                source_block_start=min(item.source_start for item in blocks),
                source_block_end=max(item.source_end for item in blocks),
                token_estimate=self.estimator.estimate(content),
                character_count=len(content),
                content_hash=content_hash,
                chunking_config_hash=request.config.config_hash,
                chunking_strategy_version=request.config.chunking_strategy_version,
                normalization_version=request.config.normalization_version,
                data_classification=request.data_classification,
                metadata_json=metadata,
            ),
        )

    def _merge_small_tail(
        self, chunks: list[ChunkCandidate], request: ChunkingRequest
    ) -> list[ChunkCandidate]:
        if len(chunks) < 2 or chunks[-1].metadata.character_count >= request.config.min_characters:
            return chunks
        previous, tail = chunks[-2], chunks[-1]
        if previous.metadata.locator != tail.metadata.locator:
            return chunks
        merged = f"{previous.content}\n\n{tail.content}"
        if len(merged) > request.config.max_characters:
            return chunks
        metadata = previous.metadata.model_copy(
            update={
                "source_block_end": tail.metadata.source_block_end,
                "token_estimate": self.estimator.estimate(merged),
                "character_count": len(merged),
                "content_hash": hashlib.sha256(merged.encode()).hexdigest(),
                "metadata_json": {**previous.metadata.metadata_json, **tail.metadata.metadata_json},
            }
        )
        return [*chunks[:-2], ChunkCandidate(content=merged, metadata=metadata)]

    @staticmethod
    def _safe_split(text: str, limit: int) -> list[str]:
        if limit < 1:
            raise ChunkingError("Chunk size leaves no room for structured content")
        if len(text) <= limit:
            return [text]
        sentences = re.split(r"(?<=[.!?。！？])\s+", text)
        pieces: list[str] = []
        current = ""
        for sentence in sentences:
            if len(sentence) > limit:
                if current:
                    pieces.append(current)
                    current = ""
                remaining = sentence
                while len(remaining) > limit:
                    split = remaining.rfind(" ", 0, limit + 1)
                    split = split if split > 0 else limit
                    pieces.append(remaining[:split].strip())
                    remaining = remaining[split:].strip()
                if remaining:
                    current = remaining
                continue
            candidate = f"{current} {sentence}".strip()
            if current and len(candidate) > limit:
                pieces.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            pieces.append(current)
        return [piece for piece in pieces if piece]

    @staticmethod
    def _overlap_tail(blocks: list[_Block], limit: int) -> list[_Block]:
        if limit == 0:
            return []
        tail: list[_Block] = []
        size = 0
        for block in reversed(blocks):
            added = len(block.text) + (2 if tail else 0)
            if size + added > limit:
                break
            tail.insert(0, block)
            size += added
        return tail

    @staticmethod
    def _join(blocks: list[_Block]) -> str:
        return "\n\n".join(item.text for item in blocks).strip()

    @staticmethod
    def _is_list(text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return len(lines) > 1 and all(
            re.match(r"^(?:[-*•]|\d+[.)])\s+", line) is not None for line in lines
        )

    @staticmethod
    def _section_path(section: ParsedSection) -> str | None:
        value = section.metadata.get("section_path")
        if isinstance(value, list):
            return " > ".join(str(item) for item in value if str(item).strip()) or None
        if isinstance(value, str) and value.strip():
            return value.strip()
        return section.title

    @staticmethod
    def _merge_metadata(blocks: list[_Block]) -> dict[str, Any]:
        if not blocks:
            return {}
        kinds = {item.metadata.get("block_type") for item in blocks}
        if len(kinds) != 1:
            return {"block_type": "mixed"}
        result = dict(blocks[0].metadata)
        for key in ("row_start", "item_start"):
            values = [
                item.metadata.get(key) for item in blocks if item.metadata.get(key) is not None
            ]
            if values:
                result[key] = min(values)
        for key in ("row_end", "item_end"):
            values = [
                item.metadata.get(key) for item in blocks if item.metadata.get(key) is not None
            ]
            if values:
                result[key] = max(values)
        return result
