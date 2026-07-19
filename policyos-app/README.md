# PolicyOS MVP

PolicyOS는 지방의회 의원실의 정책기획, 근거관리, 우선순위 결정과 실행관리를
지원하는 AI 업무 플랫폼입니다.

## 현재 구현

- FastAPI API와 OpenAPI 문서
- PostgreSQL 비동기 연결
- Redis 개발 서비스
- Alembic 스키마 마이그레이션
- Organization, User, Membership
- Role, Permission, MembershipRole, RolePermission 기반 RBAC 데이터 모델
- AuditEvent와 정책 후보 생성 감사기록
- 정책 후보 생성·목록·상세 API
- Ruff 및 Pytest 검증

## Windows PowerShell 실행

Docker Desktop이 설치되고 실행 중이어야 합니다.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

API 컨테이너는 시작할 때 `alembic upgrade head`를 먼저 실행합니다.

접속 주소:

- API 문서: `http://localhost:8000/docs`
- 상태 확인: `http://localhost:8000/health`

## 마이그레이션 명령

```powershell
docker compose run --rm api alembic current
docker compose run --rm api alembic history
docker compose run --rm api alembic upgrade head
```

개발 중 새 모델 변경을 마이그레이션으로 생성할 때:

```powershell
docker compose run --rm api alembic revision --autogenerate -m "describe change"
```

운영 환경에서는 생성된 마이그레이션을 반드시 검토한 후 적용해야 합니다.

## 정책 후보 API 호환성

기존 요청 본문은 변경하지 않았습니다.

```powershell
$body = @{
  title = "산재공공병원 연계 소아응급센터"
  summary = "범서권 소아응급 접근성 개선을 위한 운영모델 검토"
  candidate_type = "public_service"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/policy-candidates" `
  -ContentType "application/json" `
  -Body $body
```

정책 후보 생성은 같은 트랜잭션에서 `policy_candidate.created` 감사 이벤트도 기록합니다.
현재 인증 API가 아직 없으므로 행위자 사용자와 조직은 비어 있을 수 있습니다.
2단계 인증·인가 구현 시 현재 사용자와 멤버십이 자동 연결됩니다.

## 로컬 품질검사

Python 3.12 환경에서 개발 의존성을 설치한 뒤 실행합니다.

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest -q
```

## 다음 구현 단계

1. 인증과 현재 사용자 컨텍스트
2. RBAC 인가 의존성 및 관리 API
3. 감사 이벤트 조회 API
4. 정책 후보 조직 격리
5. 정책 후보 Screening 및 Assessment
