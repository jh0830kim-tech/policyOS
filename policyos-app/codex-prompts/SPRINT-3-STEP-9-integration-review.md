# Sprint 3 Step 9 — Integration Tests and Review


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
FakeModelGateway로 전체 AI Office 흐름을 검증하세요.

## E2E
1. agent.execute 권한 사용자가 policy task 생성
2. Chief Secretary가 Policy Agent로 routing
3. prompt registry와 fake gateway 사용
4. structured result 반환
5. task/run DB 기록
6. authorized 조회
7. unauthorized/cross-org 차단
8. combined request 두 Agent 실행
9. partial failure -> needs_review
10. network call 없음

## 최종 검토
- async boundary
- organization scope
- prompt/model metadata
- safe errors
- hidden reasoning/secrets 저장 없음
- dead code/duplicate 제거
- architecture, AI Office, API, DB, security, roadmap, changelog 업데이트

실행:
- `git diff --check`
- `ruff check .`
- `pytest`

commit/push는 하지 말고 변경 파일, endpoint, migration, test 수, warnings, deferred live provider/RAG를 보고하세요.
