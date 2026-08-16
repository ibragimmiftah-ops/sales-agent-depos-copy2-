"""Authentication endpoints: operator login and public chat token."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_operator_token, create_public_chat_token
from app.core.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/token", response_model=TokenResponse)
async def login(
    request: TokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token = await create_operator_token(db, request.email, request.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=token)


@router.post("/public-token", response_model=TokenResponse)
async def public_token(
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Issue an anonymous chat-scoped token for the public widget."""
    token = await create_public_chat_token(db)
    return TokenResponse(access_token=token)
