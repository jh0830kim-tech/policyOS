from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.identity import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse
from app.services.authentication import authenticate_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Rate limiting belongs at the API gateway or a dedicated FastAPI dependency before
    # credential verification. See docs/04_SECURITY/SECURITY.md.
    access_token = await authenticate_user(
        db,
        payload.email,
        payload.password,
        request_id=request.headers.get("x-request-id"),
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=CurrentUserResponse)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
