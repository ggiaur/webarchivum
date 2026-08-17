"""Real, asyncpg-backed CRUD for the `users` table (spec/schema.sql).
Replaces app/api/v1/auth.py's previous MOCK_USERS_DB — a hardcoded dict of
two fixture accounts, the only thing about this session's login/refresh
flow that wasn't already real (password hashing, JWT signing, and RBAC
role checks were always genuine)."""

from typing import Any, Dict, List, Optional

import asyncpg

_USER_COLUMNS = "id, tenant_id, email, password_hash, role, full_name, is_active"


def _row_to_user(row: asyncpg.Record) -> Dict[str, Any]:
    user = dict(row)
    user["id"] = str(user["id"])
    user["tenant_id"] = str(user["tenant_id"])
    return user


async def get_user_by_email(conn: asyncpg.Connection, email: str) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow(
        f"SELECT {_USER_COLUMNS} FROM users WHERE email = $1 AND deleted_at IS NULL", email,
    )
    return _row_to_user(row) if row else None


async def get_user_by_id(conn: asyncpg.Connection, user_id: str) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow(
        f"SELECT {_USER_COLUMNS} FROM users WHERE id = $1 AND deleted_at IS NULL", user_id,
    )
    return _row_to_user(row) if row else None


async def list_users(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        f"SELECT {_USER_COLUMNS} FROM users WHERE deleted_at IS NULL ORDER BY created_at ASC"
    )
    return [_row_to_user(r) for r in rows]


async def create_user(
    conn: asyncpg.Connection,
    email: str,
    password_hash: str,
    role: str,
    full_name: str,
    tenant_id: str = "00000000-0000-0000-0000-000000000001",
) -> Dict[str, Any]:
    row = await conn.fetchrow(
        f"""
        INSERT INTO users (tenant_id, email, password_hash, role, full_name, is_active)
        VALUES ($1, $2, $3, $4, $5, TRUE)
        RETURNING {_USER_COLUMNS}
        """,
        tenant_id, email.lower().strip(), password_hash, role, full_name,
    )
    return _row_to_user(row)


async def update_user(
    conn: asyncpg.Connection,
    user_id: str,
    role: Optional[str] = None,
    full_name: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    updates = []
    params = [user_id]
    idx = 2

    if role is not None:
        updates.append(f"role = ${idx}")
        params.append(role)
        idx += 1
    if full_name is not None:
        updates.append(f"full_name = ${idx}")
        params.append(full_name)
        idx += 1
    if is_active is not None:
        updates.append(f"is_active = ${idx}")
        params.append(is_active)
        idx += 1

    if not updates:
        existing = await get_user_by_id(conn, user_id)
        if not existing:
            raise ValueError(f"User {user_id} not found.")
        return existing

    set_clause = ", ".join(updates)
    row = await conn.fetchrow(
        f"""
        UPDATE users
        SET {set_clause}
        WHERE id = $1 AND deleted_at IS NULL
        RETURNING {_USER_COLUMNS}
        """,
        *params,
    )
    if not row:
        raise ValueError(f"User {user_id} not found.")
    return _row_to_user(row)
