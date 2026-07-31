import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.db import get_db_connection
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.api.deps import get_current_user_payload
from app.crud import users as users_crud
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# In-memory blacklist for revoked refresh tokens (dev/testing; production uses Redis db=1)
_revoked_tokens: set[str] = set()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserSummary(BaseModel):
    id: str
    email: str
    role: str
    full_name: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserSummary


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, conn: asyncpg.Connection = Depends(get_db_connection)):
    user = await users_crud.get_user_by_email(conn, body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen email vagy jelszó.",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Fiók inaktív.",
        )

    access_token = create_access_token(
        subject=user["id"],
        role=user["role"],
        tenant_id=user["tenant_id"],
    )
    refresh_token = create_refresh_token(
        subject=user["id"],
        tenant_id=user["tenant_id"],
    )

    await users_crud.mark_login(conn, user["id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=3600,
        user=UserSummary(
            id=user["id"],
            email=user["email"],
            role=user["role"],
            full_name=user["full_name"],
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(body: RefreshTokenRequest, conn: asyncpg.Connection = Depends(get_db_connection)):
    if body.refresh_token in _revoked_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A megadott refresh token vissza lett vonva.",
        )

    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Érvénytelen token típus.",
            )

        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")

        try:
            user = await users_crud.get_user_by_id(conn, user_id)
        except asyncpg.DataError:
            user = None
        if not user or not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Felhasználó nem található vagy inaktív.",
            )

        new_access_token = create_access_token(
            subject=user["id"],
            role=user["role"],
            tenant_id=tenant_id,
        )
        new_refresh_token = create_refresh_token(
            subject=user["id"],
            tenant_id=tenant_id,
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=3600,
            user=UserSummary(
                id=user["id"],
                email=user["email"],
                role=user["role"],
                full_name=user["full_name"],
            ),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest, _payload: dict = Depends(get_current_user_payload)):
    _revoked_tokens.add(body.refresh_token)
    return None
