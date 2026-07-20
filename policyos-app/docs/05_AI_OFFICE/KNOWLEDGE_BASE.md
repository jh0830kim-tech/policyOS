# Knowledge Base

Potential sources:
- ordinances and laws
- council minutes
- official reports
- budget documents
- policy research
- internal office procedures
- approved correspondence templates
- public datasets

Each source needs:
- owner
- organization scope
- classification
- effective date
- version
- retention rule
- ingestion status
## Sprint 6 knowledge domain

The persisted lineage is `KnowledgeSource -> KnowledgeDocument -> KnowledgeDocumentVersion -> KnowledgeChunk`. Every row carries organization scope, and child records use composite `(parent_id, organization_id)` foreign keys so a record cannot be attached to a parent from another organization.

Document versions preserve title, language, classification, effective/retrieved dates, version number, content hash, status, metadata, creator, and timestamps. Version identity and content-bearing metadata are immutable after insertion; status may advance during ingestion. A changed document must create a new monotonically numbered version. Unique constraints reject duplicate version numbers and duplicate content hashes within a document.

`KnowledgeIngestionJob` records safe lifecycle metadata, `KnowledgeAccessPolicy` represents source/classification permission boundaries, and `CitationReference` preserves document/version/chunk lineage plus source title/type, location, dates, version, and content hash. Retrieval, parsing, chunk generation, and embedding behavior are added by later Sprint 6 checkpoints.
## Secure ingestion pipeline

The ingestion sequence is validate → create pending job → scan → duplicate check → parse → normalize → create/find document → append immutable version → finalize job. TXT, Markdown, PDF text, DOCX, CSV, and XLSX are supported. HWP/HWPX use an adapter that returns an explicit unsupported error. Page, heading, table, sheet, row/column, parser version, normalization version, and optional effective/meeting/fiscal metadata are retained without inferring uncertain official metadata.
## Deterministic chunking and citation

Strategy version `1.0.0` prioritizes section, heading, paragraph, list, table, sentence, then hard character boundaries. Defaults are max 4,000, target 3,000, overlap 300, and minimum 200 characters. Page/section/table/list boundaries are preserved by default. Tables repeat known headers when split and retain sheet/row ranges; lists retain marker type and item ranges. Missing pages or sections remain null rather than being inferred.

Each chunk records its source block range, locator, SHA-256, character count, heuristic token estimate, normalization/strategy versions, config hash, and inherited classification. Citation labels use source-type-specific formatting and omit unavailable values. Citation completeness is `complete`, `partial`, or `insufficient`; insufficient locators are passed forward as warnings rather than treated as official evidence.
