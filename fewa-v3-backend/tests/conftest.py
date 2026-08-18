import os
import asyncpg
import pytest

os.environ.setdefault("POSTGRES_PORT", "5460")
os.environ.setdefault("POSTGRES_USER", "fewa_admin")
os.environ.setdefault("POSTGRES_PASSWORD", "fewa_dev_local_only")
os.environ.setdefault("POSTGRES_DB", "fewa_v3")
os.environ.setdefault("REDIS_PORT", "6380")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9002")
os.environ.setdefault("MINIO_ACCESS_KEY", "miniotestadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "miniotestpassword")


def get_test_dsn():
    if "TEST_DATABASE_URL" in os.environ:
        return os.environ["TEST_DATABASE_URL"]
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5460")
    user = os.environ.get("POSTGRES_USER", "fewa_admin")
    pw = os.environ.get("POSTGRES_PASSWORD", "fewa_dev_local_only")
    db = os.environ.get("POSTGRES_DB", "fewa_v3")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


CLEANUP_SQL = """
ALTER TABLE release_decisions DISABLE TRIGGER trg_arch01_release_decision_immutable;
ALTER TABLE release_decisions DISABLE TRIGGER trg_arch01_release_decision_guard;

DELETE FROM release_decisions WHERE snapshot_id IN (
    SELECT id FROM archived_snapshots WHERE site_id IN (
        SELECT id FROM sites WHERE domain LIKE 'jobsapi-%' OR domain LIKE 'test-%' OR domain LIKE 'site-%'
    )
);
DELETE FROM lifecycle_events WHERE snapshot_id IN (
    SELECT id FROM archived_snapshots WHERE site_id IN (
        SELECT id FROM sites WHERE domain LIKE 'jobsapi-%' OR domain LIKE 'test-%' OR domain LIKE 'site-%'
    )
);
DELETE FROM archived_snapshots WHERE site_id IN (
    SELECT id FROM sites WHERE domain LIKE 'jobsapi-%' OR domain LIKE 'test-%' OR domain LIKE 'site-%'
);
DELETE FROM sites WHERE domain LIKE 'jobsapi-%' OR domain LIKE 'test-%' OR domain LIKE 'site-%';
DELETE FROM users WHERE email LIKE 'testuser-%@%' OR email LIKE 'newuser-%@%';

ALTER TABLE release_decisions ENABLE ALWAYS TRIGGER trg_arch01_release_decision_immutable;
ALTER TABLE release_decisions ENABLE ALWAYS TRIGGER trg_arch01_release_decision_guard;
"""


async def _purge_test_records():
    dsn = get_test_dsn()
    try:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await conn.execute(CLEANUP_SQL)
        finally:
            await conn.close()
    except Exception:
        pass


@pytest.fixture(autouse=True)
async def auto_clean_test_db():
    """Autouse fixture that purges leftover test domain/user records before and after every test,
    ensuring 0 test pollution leakage even if assertions fail or tests abort mid-execution.
    """
    await _purge_test_records()
    yield
    await _purge_test_records()

