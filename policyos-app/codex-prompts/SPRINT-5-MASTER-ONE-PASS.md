# Codex Master Prompt — Sprint 5 OpenAI Provider Integration

작업 전 읽기:

- `CODEX.md`
- `POLICYOS_CONSTITUTION.md`
- Sprint 3/4 AI architecture, security, API, prompt, workflow 문서
- `specs/SPRINT-5-SPEC.md`
- `specs/ADR-010-openai-responses-api.md`
- `specs/ADR-011-provider-secret-management.md`
- `specs/ADR-012-model-usage-telemetry.md`

## Branch safety

현재 브랜치가 아래와 다르면 중단하세요.

```text
feature/sprint-5-openai-provider
```

## 공통 규칙

- 기존 ModelGateway 계약을 보존하세요.
- OpenAI 어댑터가 Agent 도메인에 직접 침투하지 않게 하세요.
- 공식 OpenAI Python SDK와 Responses API를 사용하세요.
- API 키를 코드, 로그, DB, 테스트 fixture에 넣지 마세요.
- CI와 단위 테스트는 실제 API 호출 없이 통과해야 합니다.
- hidden chain-of-thought를 요청·저장·노출하지 마세요.
- 최종 구조화 출력, 근거, 경고, usage, provider request id만 저장하세요.
- 자동 commit/push는 마지막 승인 전까지 금지합니다.
- 각 Phase 후 `ruff check .`와 `pytest`, 실패 시 중단하세요.

## PHASE 1 — Configuration and dependencies

1. 공식 `openai` Python SDK를 production dependency로 추가하세요.
2. Settings에 최소 다음을 추가하세요.
   - `openai_api_key`
   - `openai_model`
   - `openai_timeout_seconds`
   - `openai_max_retries`
   - `openai_store_responses`
3. 실제 secret은 `.env`에만 두고 `.env.example`에는 placeholder만 작성하세요.
4. API 키 미설정 시 애플리케이션 전체가 무조건 죽지 않게 하고, OpenAI provider 선택 시에만 명확한 configuration error를 발생시키세요.
5. production 환경에서 빈 키 또는 약한 설정을 안전하게 검증하세요.

테스트 후 Ruff/Pytest.

## PHASE 2 — OpenAI Responses adapter

기존 ModelGateway를 구현하는 `OpenAIResponsesGateway`를 추가하세요.

권장 위치:
`app/ai/providers/openai_responses.py`

요구사항:
- AsyncOpenAI 사용
- `client.responses.create(...)`
- model, instructions/input, timeout 적용
- provider response id 수집
- output text/structured output 추출
- usage metadata 매핑
- completed/failed/incomplete 상태 처리
- OpenAI 예외를 PolicyOS typed error로 변환
- API 키나 raw sensitive payload를 로그에 남기지 않음
- dependency injection으로 client 또는 transport 대체 가능

실제 네트워크를 호출하지 않는 mocked SDK 테스트를 추가하세요.

## PHASE 3 — Structured Outputs

Agent의 Pydantic schema를 JSON Schema로 변환하여 OpenAI Structured Outputs를 사용하세요.

요구사항:
- JSON Schema strict mode를 우선 사용
- Agent별 output schema 명칭은 안정적이어야 함
- schema validation 실패를 typed provider/output error로 변환
- 구형 JSON object mode에 의존하지 않음
- refusal 또는 incomplete output 처리
- raw JSON을 신뢰하지 말고 최종 Pydantic 검증 수행

Budget, Statistics, Speech, PR, SNS, PPT, Policy Research, Legal Review 결과에 적용 가능한 공통 변환 계층을 구현하세요.

테스트:
- 정상 structured output
- invalid schema response
- refusal
- incomplete response
- missing required field
- unexpected extra field 정책

## PHASE 4 — Provider registry and selection

기존 Gateway 선택 구조를 확장하세요.

지원:
- `fake`
- `disabled`
- `openai`

요구사항:
- 설정에 따라 provider 선택
- Agent가 provider 이름을 알 필요 없음
- 테스트 환경 기본값은 fake
- production에서 명시적 provider 설정
- 지원하지 않는 provider는 safe configuration error
- 향후 Claude/Gemini/Ollama를 쉽게 추가할 수 있는 factory/registry

테스트.

## PHASE 5 — Timeout, retry, cancellation

운영 정책을 구현하세요.

- 전체 request timeout
- SDK retry와 애플리케이션 retry의 중복을 피함
- retry 가능한 오류와 불가능한 오류 구분
- exponential backoff 또는 SDK 정책을 문서화
- cancellation propagation
- rate-limit error를 typed error로 변환
- 4xx validation/auth 오류는 무분별하게 retry하지 않음
- 최대 시도 횟수 기록

테스트:
timeout, rate limit, auth error, server error, cancellation, retry count.

## PHASE 6 — Usage and cost telemetry

AI task/agent run 기록을 확장하세요.

저장:
- provider
- model
- response/request id
- input tokens
- output tokens
- total tokens
- cached tokens가 제공되면 해당 값
- latency
- retry count
- success/failure
- estimated cost nullable
- started/finished time

규칙:
- 가격표를 코드에 하드코딩하지 말고 versioned pricing configuration 또는 nullable cost를 사용
- raw prompt나 secret을 telemetry에 저장하지 않음
- organization/user/task 단위 집계가 가능하도록 함

Alembic migration과 테스트.

## PHASE 7 — Data retention and privacy

OpenAI 호출 설정과 PolicyOS 저장 정책을 명시하세요.

- `store` 설정을 configurable하게 관리
- 기본값을 보수적으로 선택하고 문서화
- 내부·민감 문서 전달 최소화
- prompt/context 분류와 redaction hook
- 외부 provider로 보낸 데이터의 audit metadata
- Zero Data Retention 또는 조직 정책과 충돌 가능한 기능을 문서화
- raw provider response 장기 저장 금지

문서와 테스트 가능한 configuration behavior를 추가하세요.

## PHASE 8 — Live smoke test command

운영자가 명시적으로 실행할 때만 실제 OpenAI 호출을 하는 별도 명령을 추가하세요.

예:
`python -m scripts.openai_smoke_test`

요구사항:
- API 키 존재 확인
- 작은 비민감 테스트 prompt
- configured model 사용
- structured output 검증
- response id, latency, token usage만 출력
- API 키와 전체 raw response는 출력하지 않음
- 일반 pytest에서 자동 실행 금지
- `RUN_OPENAI_LIVE_TESTS=1` 같은 명시적 opt-in이 있을 때만 integration marker 실행 가능

## PHASE 9 — Application integration

Sprint 4의 Work Package 실행 경로에서 configured gateway를 실제로 사용하도록 production application service를 연결하세요.

요구사항:
- fake/real gateway 전환 가능
- thin router
- active membership/RBAC/organization isolation 유지
- provider 실패 시 task/run/artifact 상태가 정확히 기록
- 부분 실패는 needs_review
- request timeout 초과 시 safe API error
- 공개 API 응답에 provider secret/raw payload 미노출

mocked OpenAI adapter를 사용한 API integration 테스트를 추가하세요.

## PHASE 10 — Documentation and final review

업데이트:
- AI architecture
- provider configuration
- security/privacy
- API behavior
- telemetry
- operations/runbook
- roadmap
- changelog
- `.env.example`

최종 실행:
```bash
git diff --check
ruff check .
pytest
git status
```

실제 API 키 없이 모두 통과해야 합니다.

commit/push하지 말고 보고:
1. 파일 목록
2. OpenAI adapter 구조
3. Structured Outputs 방식
4. provider selection
5. timeout/retry 정책
6. usage telemetry/migration
7. privacy/store 설정
8. smoke test 방법
9. API integration
10. 테스트 수
11. Ruff/diff 결과
12. 기술부채
13. Sprint 6 RAG 전 남은 작업
14. 권장 commit 분할
