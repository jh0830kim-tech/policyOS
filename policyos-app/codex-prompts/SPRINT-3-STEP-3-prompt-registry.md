# Sprint 3 Step 3 — Prompt Registry and Versioning


작업 전 다음 문서를 읽으세요.

- `CODEX.md`
- `POLICYOS_CONSTITUTION.md`
- `docs/01_ARCHITECTURE/ARCHITECTURE.md`
- `docs/01_ARCHITECTURE/AI_ARCHITECTURE.md`
- `docs/05_AI_OFFICE/AI_OFFICE.md`
- `docs/05_AI_OFFICE/AGENTS.md`
- `docs/05_AI_OFFICE/SYSTEM_PROMPTS.md`
- `docs/05_AI_OFFICE/WORKFLOW.md`
- `specs/epics/EPIC-002-ai-office.md`

기존 코드를 먼저 조사하고 Sprint 2의 인증, 조직 격리, RBAC, 테스트, CI를 보존하세요.

공통 규칙:
- 테스트에서 외부 네트워크를 사용하지 마세요.
- 공급자 API 키를 하드코딩하지 마세요.
- 숨겨진 chain-of-thought를 요청하거나 저장하지 마세요.
- 자동 commit/push는 해당 프롬프트에서 명시적으로 허용할 때만 수행하세요.
- 완료 후 `ruff check .`와 `pytest`를 실행하세요.


## 목표
Python 코드에 시스템 프롬프트를 흩어놓지 않고 승인된 prompt를 버전 관리하는 registry를 구현하세요.

## 요구사항
- agent name, prompt name, semantic version, content hash, status, source path
- 기존 `prompts/`에서 안전하게 로드
- missing, empty, duplicate 검증
- agent와 version으로 명시적 선택
- deterministic SHA-256 content hash
- 테스트용 in-memory source
- user input을 system instruction과 분리
- path traversal 차단

## 권장 위치
`app/ai/prompts.py`

## 테스트
정상 로드, 동일 hash, missing, duplicate, traversal 차단, version 선택.
