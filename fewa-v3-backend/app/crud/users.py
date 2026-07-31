"""Real, asyncpg-backed CRUD for the `users` table (spec/schema.sql).
Replaces app/api/v1/auth.py's previous MOCK_USERS_DB — a hardcoded dict of
two fixture accounts, the only thing about this session's login/refresh
flow that wasn't already real (password hashing, JWT signing, and RBAC
role checks were always genuine)."""

from typing import Any, Dict, Optional

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


async def mark_login(conn: asyncpg.Connection, user_id: str) -> None:
    await conn.execute("UPDATE users SET last_login_at = now() WHERE id = $1", user_id)
