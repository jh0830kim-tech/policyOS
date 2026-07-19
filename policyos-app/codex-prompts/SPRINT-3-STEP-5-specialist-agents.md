# Sprint 3 Step 5 — Initial Specialist Agents


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
첫 전문 Agent 두 개를 구현하세요.
- Policy Research Agent
- Legal Review Agent

## Policy Research output
policy question, current situation, findings, comparable cases, stakeholders, policy options, trade-offs, evidence gaps, next research, evidence references.

## Legal Review output
legal question, authorities, provisions, interpretation, uncertainty, procedural requirements, risks, counsel escalation, evidence references/effective dates.

## 구조
- 공통 Agent contract 구현
- gateway와 prompt registry를 constructor injection
- structured output 검증
- fake gateway로 테스트
- 직접 web search/무제한 DB 접근 금지

## 테스트
metadata, capabilities, prompt 선택, 정상 output, invalid model output, evidence, gateway error.
