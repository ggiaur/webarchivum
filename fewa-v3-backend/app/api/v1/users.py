import uuid
from typing import Optional, List, Literal
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.core.db import get_db_connection
from app.core.security import hash_password
from app.api.deps import require_role
from app.crud import users as users_crud

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])

ValidRole = Literal["admin", "archivist", "curator", "indexer", "viewer", "guest"]


class UserCreateSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: ValidRole
    full_name: str = Field(..., min_length=1)


class UserUpdateSchema(BaseModel):
    role: Optional[ValidRole] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("", dependencies=[Depends(require_role("admin"))])
async def list_users_endpoint(conn: asyncpg.Connection = Depends(get_db_connection)):
    """List all registered users (admin only)."""
    user_list = await users_crud.list_users(conn)
    # Strip password_hash from response
    for u in user_list:
        u.pop("password_hash", None)
    return {"items": user_list, "total": len(user_list)}


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role("admin"))])
async def create_user_endpoint(
    body: UserCreateSchema,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Create a new user with a hashed password (admin only)."""
    existing = await users_crud.get_user_by_email(conn, str(body.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ez az email cím ({body.email}) már regisztrálva van.",
        )

    hashed_pw = hash_password(body.password)
    user = await users_crud.create_user(
        conn,
        email=str(body.email),
        password_hash=hashed_pw,
        role=body.role,
        full_name=body.full_name,
    )
    user.pop("password_hash", None)
    return user


@router.patch("/{user_id}")
async def update_user_endpoint(
    user_id: uuid.UUID,
    body: UserUpdateSchema,
    conn: asyncpg.Connection = Depends(get_db_connection),
    current_user: dict = Depends(require_role("admin")),
):
    """Update user role, full_name, or active status (admin only).
    Prevents admins from deactivating or demoting their own account."""
    target_id = str(user_id)
    actor_id = current_user.get("sub")

    if target_id == actor_id:
        if body.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Saját fiókodat nem inaktiválhatod.",
            )
        if body.role is not None and body.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Saját admin jogosultságodat nem vonhatod vissza.",
            )

    try:
        updated = await users_crud.update_user(
            conn,
            user_id=target_id,
            role=body.role,
            full_name=body.full_name,
            is_active=body.is_active,
        )
        updated.pop("password_hash", None)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
