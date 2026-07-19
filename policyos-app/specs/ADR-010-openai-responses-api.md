# ADR-010 — OpenAI Responses API

PolicyOS의 OpenAI 어댑터는 공식 SDK의 Responses API를 사용합니다. Agent별 구조화 산출물은 가능한 경우 strict JSON Schema Structured Outputs로 요청하고, 반환값은 다시 Pydantic으로 검증합니다.
