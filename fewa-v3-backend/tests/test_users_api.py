import os
import uuid
import asyncpg
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.v1.users import router as users_router
from app.core.db import get_db_connection
from app.core.security import create_access_token

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://fewa_bootstrap:local_bootstrap_pw@postgres:5432/fewa_db",
)

ADMIN_ID = "00000000-0000-0000-0000-000000000099"
CURATOR_ID = "550e8400-e29b-41d4-a716-446655440000"

ADMIN_TOKEN = create_access_token(
    subject=ADMIN_ID,
    role="admin",
    tenant_id="00000000-0000-0000-0000-000000000001",
)
CURATOR_TOKEN = create_access_token(
    subject=CURATOR_ID,
    role="curator",
    tenant_id="00000000-0000-0000-0000-000000000001",
)


async def _override_get_db_connection():
    connection = await asyncpg.connect(dsn=TEST_DSN)
    try:
        yield connection
    finally:
        await connection.close()


app = FastAPI()
app.include_router(users_router)
app.dependency_overrides[get_db_connection] = _override_get_db_connection

client = TestClient(app)


@pytest.fixture
async def conn():
    try:
        connection = await asyncpg.connect(dsn=TEST_DSN)
    except (OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"Test Postgres not reachable: {e}")
        return
    yield connection
    await connection.close()


@pytest.mark.asyncio
async def test_list_users_rbac_and_content(conn):
    # Non-admin curator gets 403
    forbidden_res = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
    )
    assert forbidden_res.status_code == status.HTTP_403_FORBIDDEN

    # Admin gets 200 and list
    success_res = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    )
    assert success_res.status_code == status.HTTP_200_OK
    items = success_res.json()["items"]
    assert len(items) >= 2
    assert "password_hash" not in items[0]


@pytest.mark.asyncio
async def test_create_and_update_user_flow(conn):
    new_email = f"testuser-{uuid.uuid4().hex[:6]}@vmk.hu"
    create_res = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={
            "email": new_email,
            "password": "Password123!",
            "role": "indexer",
            "full_name": "Test Indexer",
        },
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    user_data = create_res.json()
    user_id = user_data["id"]
    assert user_data["email"] == new_email
    assert user_data["role"] == "indexer"

    # Duplicate email rejected
    dup_res = client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={
            "email": new_email,
            "password": "Password123!",
            "role": "indexer",
            "full_name": "Test Indexer",
        },
    )
    assert dup_res.status_code == status.HTTP_409_CONFLICT

    # Update role to curator
    update_res = client.patch(
        f"/api/admin/users/{user_id}",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={"role": "curator", "full_name": "Updated Indexer"},
    )
    assert update_res.status_code == status.HTTP_200_OK
    assert update_res.json()["role"] == "curator"
    assert update_res.json()["full_name"] == "Updated Indexer"

    # Self-deactivation by admin is blocked
    self_deact_res = client.patch(
        f"/api/admin/users/{ADMIN_ID}",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={"is_active": False},
    )
    assert self_deact_res.status_code == status.HTTP_400_BAD_REQUEST

    # Self-demotion by admin is blocked
    self_demote_res = client.patch(
        f"/api/admin/users/{ADMIN_ID}",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={"role": "curator"},
    )
    assert self_demote_res.status_code == status.HTTP_400_BAD_REQUEST

    # Cleanup
    await conn.execute("DELETE FROM users WHERE id = $1", uuid.UUID(user_id))
