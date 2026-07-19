from app.schemas.policy_candidate import PolicyCandidateCreate


def test_policy_candidate_request_contract_is_unchanged() -> None:
    payload = PolicyCandidateCreate(
        title="제조업 AI 전환 지원",
        summary="지역 제조기업의 AI 도입을 지원하는 정책 후보",
        candidate_type="industry_strategy",
    )
    assert payload.model_dump() == {
        "title": "제조업 AI 전환 지원",
        "summary": "지역 제조기업의 AI 도입을 지원하는 정책 후보",
        "candidate_type": "industry_strategy",
    }
