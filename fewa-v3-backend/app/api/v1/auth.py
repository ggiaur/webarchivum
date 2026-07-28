import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.api.deps import get_current_user_payload
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


# Mock user database for Auth testing / default admin seed
MOCK_USERS_DB = {
    "curator@vmk.hu": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "curator@vmk.hu",
        "password_hash": hash_password("SecretPassword123!"),
        "role": "curator",
        "full_name": "VMK Kurátor",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "is_active": True,
    },
    "admin@vmk.hu": {
        "id": "00000000-0000-0000-0000-000000000099",
        "email": "admin@vmk.hu",
        "password_hash": hash_password("AdminPassword123!"),
        "role": "admin",
        "full_name": "System Admin",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "is_active": True,
    },
}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = MOCK_USERS_DB.get(body.email)
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
def refresh_tokens(body: RefreshTokenRequest):
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

        # Find user
        user = next((u for u in MOCK_USERS_DB.values() if u["id"] == user_id), None)
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
