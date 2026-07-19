# Sprint 3 Step 1 — Agent Domain Contracts


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
모든 AI Agent가 공통으로 사용하는 공급자 독립적 도메인 계약을 구현하세요.

## 구현 대상
- Agent identifier
- Agent capability
- Agent task
- Agent context
- Agent result
- Evidence reference
- Agent status
- Review status
- Structured error
- Usage metadata

## 요구사항
1. FastAPI, SQLAlchemy, 특정 LLM SDK에 의존하지 않아야 합니다.
2. AgentTask에는 task id, user id, organization id, task type, instruction, allowed agents/capabilities, context references가 포함되어야 합니다.
3. AgentResult는 verified findings, analysis, assumptions, recommendations, evidence, warnings를 구분해야 합니다.
4. 상태는 pending, running, succeeded, failed, needs_review를 지원하세요.
5. UTC timezone-aware timestamp를 사용하세요.
6. 입력 길이와 빈 instruction을 검증하세요.
7. 아직 DB 저장은 구현하지 마세요.

## 권장 위치
`app/ai/domain.py`

## 테스트
- 정상 task 생성
- 빈 instruction 거부
- 구조화 result
- evidence 검증
- enum/status
- 프레임워크 독립성
