import uuid

from app.knowledge.chunking import (
    ChunkingConfig,
    ChunkingRequest,
    DeterministicChunker,
    FakeTokenEstimator,
)
from app.knowledge.schemas import ParsedDocument, ParsedSection


def parsed(*sections: ParsedSection) -> ParsedDocument:
    return ParsedDocument(
        text="\n\n".join(section.text for section in sections),
        sections=list(sections),
        parser_name="test",
        parser_version="1",
    )


def request(document: ParsedDocument, config: ChunkingConfig) -> ChunkingRequest:
    return ChunkingRequest(
        organization_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        data_classification="internal",
        parsed_document=document,
        config=config,
    )


def config(**updates) -> ChunkingConfig:
    values = {
        "max_characters": 120,
        "target_characters": 70,
        "overlap_characters": 0,
        "min_characters": 10,
    }
    values.update(updates)
    return ChunkingConfig(**values)


def test_same_input_produces_identical_order_boundaries_and_hashes() -> None:
    document = parsed(
        ParsedSection(index=1, title="Scope", text="First paragraph.\n\nSecond paragraph."),
        ParsedSection(index=2, title="Effect", text="Third paragraph."),
    )
    fixed_request = request(document, config())
    first = DeterministicChunker().chunk(fixed_request)
    second = DeterministicChunker().chunk(fixed_request)
    assert first == second
    assert [item.metadata.chunk_index for item in first.chunks] == list(range(len(first.chunks)))
    assert [item.metadata.content_hash for item in first.chunks] == [
        item.metadata.content_hash for item in second.chunks
    ]


def test_paragraph_heading_page_and_section_boundaries_are_preserved() -> None:
    result = DeterministicChunker().chunk(
        request(
            parsed(
                ParsedSection(
                    index=1,
                    kind="page",
                    title="Article 1",
                    page_number=3,
                    text="Paragraph one.\n\nParagraph two.",
                    metadata={"section_path": ["Chapter I", "Article 1"]},
                ),
                ParsedSection(
                    index=2,
                    kind="page",
                    title="Article 2",
                    page_number=4,
                    text="Next page.",
                ),
            ),
            config(),
        )
    )
    assert result.chunks[0].metadata.locator.page_start == 3
    assert result.chunks[0].metadata.locator.page_end == 3
    assert result.chunks[0].metadata.locator.section_path == "Chapter I > Article 1"
    assert result.chunks[0].metadata.locator.heading == "Article 1"
    assert result.chunks[-1].metadata.locator.page_start == 4


def test_overlap_zero_and_overlap_blocks_are_deterministic() -> None:
    document = parsed(
        ParsedSection(
            index=1,
            title="Section",
            text=(
                "Alpha block text repeated.\n\nBeta block text repeated.\n\n"
                "Gamma block text repeated."
            ),
        )
    )
    without = DeterministicChunker().chunk(request(document, config(target_characters=50)))
    with_overlap = DeterministicChunker().chunk(
        request(document, config(target_characters=50, overlap_characters=35))
    )
    assert len(without.chunks) >= 2
    assert "Beta block text repeated." not in without.chunks[-1].content or len(without.chunks) == 2
    assert "Beta block text repeated." in with_overlap.chunks[-1].content
    assert all(item.metadata.character_count <= 120 for item in with_overlap.chunks)


def test_oversized_paragraph_uses_sentence_then_hard_limit() -> None:
    text = "Sentence one. " * 30 + "X" * 180
    result = DeterministicChunker().chunk(
        request(parsed(ParsedSection(index=1, text=text)), config())
    )
    assert len(result.chunks) > 2
    assert all(0 < len(item.content) <= 120 for item in result.chunks)
    assert all(item.metadata.source_block_start == 0 for item in result.chunks)


def test_small_tail_merges_when_locator_matches_and_limit_allows() -> None:
    document = parsed(ParsedSection(index=1, title="Same", text=("A" * 65) + "\n\n" + ("B" * 20)))
    result = DeterministicChunker().chunk(
        request(
            document,
            ChunkingConfig(
                max_characters=120,
                target_characters=60,
                overlap_characters=0,
                min_characters=30,
            ),
        )
    )
    assert len(result.chunks) == 1
    assert "A" * 20 in result.chunks[0].content and "B" * 20 in result.chunks[0].content


def test_table_is_atomic_or_split_by_rows_with_header_and_sheet_metadata() -> None:
    section = ParsedSection(
        index=1,
        kind="sheet",
        title="Budget",
        sheet_name="FY2026",
        start_row=1,
        end_row=8,
        text="name | amount\n" + "\n".join(f"row-{i} | {i * 100}" for i in range(1, 8)),
        metadata={"header": ["name", "amount"]},
    )
    result = DeterministicChunker().chunk(request(parsed(section), config()))
    assert all(item.content.startswith("name | amount") for item in result.chunks)
    assert all(item.metadata.metadata_json["block_type"] == "table" for item in result.chunks)
    assert all(item.metadata.metadata_json["sheet_name"] == "FY2026" for item in result.chunks)
    assert result.chunks[0].metadata.metadata_json["row_start"] == 1


def test_numbered_and_bullet_lists_preserve_markers_and_item_ranges() -> None:
    numbered = ParsedSection(index=1, title="Steps", text="1. First\n2. Second\n3. Third")
    bullet = ParsedSection(index=2, title="Items", text="- Alpha\n- Beta")
    result = DeterministicChunker().chunk(request(parsed(numbered, bullet), config()))
    assert result.chunks[0].metadata.metadata_json["list_type"] == "numbered"
    assert result.chunks[0].metadata.metadata_json["numbering_preserved"] is True
    assert result.chunks[-1].metadata.metadata_json["list_type"] == "bullet"
    assert "- Alpha" in result.chunks[-1].content


def test_chunk_hash_and_fake_token_estimate_are_stable() -> None:
    estimator = FakeTokenEstimator(42)
    result = DeterministicChunker(estimator).chunk(
        request(parsed(ParsedSection(index=1, title="A", text="Evidence text")), config())
    )
    assert result.chunks[0].metadata.token_estimate == 42
    assert len(result.chunks[0].metadata.content_hash) == 64
    assert estimator.calls == [result.chunks[0].content]
