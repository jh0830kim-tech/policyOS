from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.policy_candidate import PolicyCandidate
from app.schemas.policy_candidate import PolicyCandidateCreate, PolicyCandidateRead
from app.services.audit import record_audit_event

router = APIRouter(prefix="/policy-candidates", tags=["policy-candidates"])


@router.post("", response_model=PolicyCandidateRead, status_code=status.HTTP_201_CREATED)
async def create_policy_candidate(
    payload: PolicyCandidateCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PolicyCandidate:
    candidate = PolicyCandidate(**payload.model_dump())
    db.add(candidate)
    await db.flush()
    await record_audit_event(
        db,
        event_type="policy_candidate.created",
        resource_type="policy_candidate",
        resource_id=str(candidate.id),
        request_id=request.headers.get("x-request-id"),
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details={"candidate_type": candidate.candidate_type},
    )
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.get("", response_model=list[PolicyCandidateRead])
async def list_policy_candidates(db: AsyncSession = Depends(get_db)) -> list[PolicyCandidate]:
    result = await db.scalars(select(PolicyCandidate).order_by(PolicyCandidate.created_at.desc()))
    return list(result.all())


@router.get("/{candidate_id}", response_model=PolicyCandidateRead)
async def get_policy_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
) -> PolicyCandidate:
    try:
        candidate = await db.get(PolicyCandidate, candidate_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate id") from exc
    if candidate is None:
        raise HTTPException(status_code=404, detail="Policy candidate not found")
    return candidate
