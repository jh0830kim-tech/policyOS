# Codex Master Prompt — Sprint 6 RAG + MCP Knowledge Platform

작업 전 CODEX.md, POLICYOS_CONSTITUTION.md, RAG/MCP/Knowledge 문서와 Sprint 6 specs/ADR을 읽으세요.

현재 브랜치가 `feature/sprint-6-rag-mcp-knowledge`가 아니면 중단하세요.

공통 규칙:
- 기존 인증, RBAC, AI Office, OpenAI Provider, Privacy 기능을 보존
- organization scope와 data classification 강제
- restricted 데이터는 외부 provider/MCP로 전송 금지
- 테스트에서 외부 네트워크 호출 금지
- hidden chain-of-thought 저장 금지
- source title/type/page/section/version/effective date/content hash 보존
- 각 Checkpoint 후 git diff --check, ruff check ., pytest
- 각 Checkpoint 결과 보고 후 사용자 승인 전 commit/push 금지

## Checkpoint 1 — Knowledge Domain & Database
KnowledgeSource, KnowledgeDocument, KnowledgeDocumentVersion, KnowledgeChunk, KnowledgeIngestionJob, KnowledgeAccessPolicy, CitationReference 모델을 추가하세요.
필드: organization, source type/name, external id, title, language, classification, effective/retrieved date, version, content hash, status, metadata, creator, timestamps.
버전 덮어쓰기 금지, content hash 중복 탐지, 조직 격리, Alembic migration, 인덱스, 테스트.
권장 commit: `feat(knowledge): add knowledge domain and persistence`

## Checkpoint 2 — Secure Document Ingestion
TXT, Markdown, PDF parsed text, DOCX, CSV, XLSX를 우선 지원하세요. HWP는 adapter interface와 unsupported error만 정의 가능.
파일형식/크기/checksum/malware hook/metadata/text normalization/page-section marker/classification/version 저장/status를 구현하세요.
path traversal, executable, parser error, temp cleanup, restricted 외부 처리 금지 테스트.
권장 commit: `feat(knowledge): add secure document ingestion pipeline`

## Checkpoint 3 — Chunking & Citations
문단·제목 기반 deterministic chunking, max size/overlap, 표·목록 보존, page/section locator, chunk hash를 구현하세요.
CitationReference에 title, document/version, page/section, chunk id, effective/retrieved date, URL/internal reference, label 포함.
권장 commit: `feat(knowledge): add deterministic chunking and citations`

## Checkpoint 4 — Embeddings & Vector Retrieval
EmbeddingRequest/Response/Gateway, Fake/Disabled/OpenAI adapter, vector storage abstraction, pgvector 또는 적합한 adapter를 구현하세요.
CI 기본 fake, 실제 호출 opt-in, model/version/dimension 기록, organization/classification filter, dimension mismatch error, re-embedding 구조.
권장 commit: `feat(knowledge): add embedding and vector retrieval`

## Checkpoint 5 — Hybrid Search & Reranking
lexical + vector search, weighted fusion, metadata/date/source filters, top_k, score normalization, fake reranker를 구현하세요.
결과에 safe excerpt, scores, citation, freshness, warnings 포함. 낮은 score는 evidence insufficient.
권장 commit: `feat(knowledge): add hybrid retrieval and reranking`

## Checkpoint 6 — MCP Gateway
MCPServerDefinition, Tool/ResourceDefinition, MCPClient protocol, Fake/Disabled client, Registry, ToolPermissionPolicy, MCPAuditRecord를 구현하세요.
초기 server 정의: law-mcp, minutes-mcp, finance-mcp, internal-docs-mcp.
allowlist, organization credentials, read-only default, timeout, validation, restricted 전송 금지, write tool human approval, audit.
권장 commit: `feat(mcp): add governed MCP connector gateway`

## Checkpoint 7 — Knowledge Router
질문 유형에 따라 내부 RAG와 MCP를 선택:
법령/조례→law, 회의록→minutes, 예산→finance, 내부 문서→internal, 복합→다중.
출력: retrieval plan, consulted sources, evidence, citations, freshness warnings, access denials, evidence gaps, confidence.
rules-based, MCP 실패 시 RAG fallback, 기준일 표시, 충돌 출처 보존.
권장 commit: `feat(knowledge): add governed knowledge routing`

## Checkpoint 8 — AI Office Integration
Policy Research, Legal, Budget, Statistics, Speech, PR, PPT Agent가 Knowledge Router의 evidence package를 사용하게 연결하세요.
Agent 직접 unrestricted DB/MCP 접근 금지. citation 없는 핵심 주장은 warning. 법령 effective date/회의록 date/예산 year 보존. restricted 자료는 privacy policy 적용.
권장 commit: `feat(ai): integrate RAG and MCP evidence into office workflows`

## Checkpoint 9 — Security, Audit & Retention
source/retrieval/MCP/ingestion audit, retention, chunk/embedding cleanup, legal hold hook, reclassification, access revocation, deletion cascade를 구현하세요.
classification downgrade 금지, restricted export 금지, audit 원문 미저장, prompt injection/suspicious content flag.
권장 commit: `feat(security): add knowledge access and retention controls`

## Checkpoint 10 — E2E & Release
E2E 질문: "울산 소아응급센터 설치의 법적 근거, 관련 회의록, 예산 가능성을 종합해줘."
인증/RBAC→Knowledge Router→법령/회의록/예산/내부 RAG→Policy/Legal/Budget Agent→Chief Secretary→citations→artifact/audit/telemetry.
외부 network 없는 fake E2E, opt-in live embedding/MCP smoke test, cross-org 차단, stale/effective-date warning, citation completeness, restricted block, fallback, migration head, packaging 검증.
문서와 RELEASE_NOTES_v0.4.md, RUNBOOK 업데이트.
최종 git diff --check, ruff check ., pytest, git status.
commit/push하지 말고 전체 보고와 권장 commit 분할을 제시하세요.
