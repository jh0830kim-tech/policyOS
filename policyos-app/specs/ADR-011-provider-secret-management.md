# ADR-011 — Provider Secret Management

Provider API key는 환경변수 또는 승인된 secret manager에서만 로드합니다. 소스코드, 로그, DB, 테스트 fixture, API 응답에 저장하지 않습니다.
