"""ARCH-01 R1 role migration contract, separate from S1's 005 candidate."""
import os
from pathlib import Path

import asyncpg
import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (ROOT / "spec/migrations/006_arch_01_db_roles.sql").read_text()
R1_MIGRATOR_DSN = os.environ.get("ARCH01_R1_MIGRATOR_DATABASE_URL")


def test_006_requires_audited_bootstrap_cleanup_before_role_grants() -> None:
    assert "pg_read_server_files" in MIGRATION
    assert "bootstrap cleanup audit is required before migration 006" in MIGRATION
    assert "arch01_bootstrap_operations" in MIGRATION
    assert "ENABLE ALWAYS TRIGGER trg_lifecycle_guard" in MIGRATION


@pytest.mark.asyncio
async def test_migrator_cannot_forge_bootstrap_cleanup_audit() -> None:
    """Only the dedicated bootstrap principal may author cleanup evidence."""
    if not R1_MIGRATOR_DSN:
        pytest.skip("ARCH01_R1_MIGRATOR_DATABASE_URL is required for isolated R1 QA")
    connection = await asyncpg.connect(R1_MIGRATOR_DSN)
    transaction = connection.transaction()
    await transaction.start()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await connection.execute(
                """
                INSERT INTO public.arch01_bootstrap_operations
                    (bootstrap_session_user, stage, source_sha256,
                     started_at, completed_at, role_membership_before,
                     role_membership_after, result)
                VALUES
                    ('fewa_bootstrap', 'cleanup', repeat('0', 64), now(), now(),
                     '{"migrator_file_read": true, "app_file_read": false}'::jsonb,
                     '{"migrator_file_read": false, "app_file_read": false}'::jsonb,
                     'success')
                """
            )
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_migrator_cannot_disable_bootstrap_audit_trigger() -> None:
    """Audit enforcement remains bootstrap-owned after post-005 normalisation."""
    if not R1_MIGRATOR_DSN:
        pytest.skip("ARCH01_R1_MIGRATOR_DATABASE_URL is required for isolated R1 QA")
    connection = await asyncpg.connect(R1_MIGRATOR_DSN)
    transaction = connection.transaction()
    await transaction.start()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await connection.execute(
                "ALTER TABLE public.arch01_bootstrap_operations DISABLE TRIGGER ALL"
            )
    finally:
        await transaction.rollback()
        await connection.close()
