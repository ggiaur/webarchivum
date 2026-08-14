"""Real end-to-end test of the WACZ storage -> presigned URL -> replay
fetch chain, against the actual fewa-minio-test container and the isolated
test Postgres.

Replaces the previous version of this test, which seeded a fake dummy blob
(`b"...FEWA_WACZ_SAMPLE_ARCHIVE_DATA"`, not a valid ZIP) under a hardcoded
UUID purely so a status-code assertion against the (now-removed) live-site
`/api/proxy` endpoint would pass — it never verified real archived content
was retrievable at all. See task #40.

The uploaded bytes here are a minimal, genuinely valid ZIP archive (a real
WACZ is a ZIP container) built with Python's stdlib zipfile — not a real
Browsertrix crawl output, which is a separate, already-tested path (see
fewa-automation's own test suite and tests/test_arq_worker.py). The point
of this test is the storage/retrieval chain, not crawl content.
"""

import io
import os
import uuid
import zipfile

import asyncpg
import boto3
import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db_connection
from app.core.minio_client import MinIOClient
from app.crud import archive
from app.main import app

client = TestClient(app)

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://fewa_admin:fewa_dev_local_only@localhost:5460/fewa_v3",
)
TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def _override_get_db_connection():
    # Starlette's TestClient opens a fresh event loop per call, which
    # breaks app.core.db's lazily-cached global pool — see
    # tests/test_jobs_api.py for the full explanation.
    connection = await asyncpg.connect(dsn=TEST_DSN)
    try:
        yield connection
    finally:
        await connection.close()


def _build_minimal_valid_wacz_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pages/pages.jsonl", '{"url": "https://example.hu/", "ts": "20260730120000"}\n')
        zf.writestr("datapackage.json", '{"profile": "wacz-1.1.1"}')
    return buf.getvalue()


@pytest.mark.asyncio
async def test_real_wacz_upload_presign_and_fetch_roundtrip():
    try:
        conn = await asyncpg.connect(dsn=TEST_DSN)
    except (OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"Test Postgres not reachable at {TEST_DSN}: {e}")
        return

    minio = MinIOClient()
    try:
        minio.client.list_buckets()
    except Exception as e:
        await conn.close()
        pytest.skip(f"Test MinIO not reachable: {e}")
        return

    minio.ensure_bucket_exists()
    wacz_bytes = _build_minimal_valid_wacz_bytes()
    wacz_key = f"wacz/test/{uuid.uuid4().hex}.wacz"
    upload_info = minio.upload_wacz_stream(wacz_key, io.BytesIO(wacz_bytes))
    assert upload_info["filesize_bytes"] == len(wacz_bytes)

    domain = f"waczplayer-{uuid.uuid4().hex[:8]}.hu"
    site_row = await conn.fetchrow(
        "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
        TENANT_ID, domain, f"https://{domain}/", domain,
    )
    created = await archive.create_candidate_snapshot(
        conn, site_id=str(site_row["id"]), seed_url=f"https://{domain}/",
        dc_title="WACZ replay chain test", discovery_reason="test", discovery_metadata={},
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)
    await archive.mark_crawling(conn, created["id"])
    await archive.record_crawl_result(
        conn, created["id"], wacz_minio_path=wacz_key,
        wacz_sha256=upload_info["sha256"], wacz_filesize_bytes=upload_info["filesize_bytes"],
    )
    result = await archive.record_qc_result(
        conn, created["id"], qc_score=99, qc_detail={}, auto_accept_threshold=96,
    )
    assert result["lifecycle_status"] == "published"

    app.dependency_overrides[get_db_connection] = _override_get_db_connection
    try:
        doc_resp = client.get(f"/api/documents/{created['id']}")
        assert doc_resp.status_code == 200
        doc_data = doc_resp.json()
        assert doc_data["wacz_url"] is not None

        # The critical assertion: the URL the frontend is handed is really
        # fetchable and returns the exact bytes that were uploaded — not a
        # fabricated "it probably works" placeholder. Fetched through the
        # app itself now that wacz_url is a same-origin /api/wacz/{id} path
        # rather than a presigned MinIO URL (see search_service.py for why
        # that changed).
        fetch_resp = client.get(doc_data["wacz_url"])
        assert fetch_resp.status_code == 200
        assert fetch_resp.content == wacz_bytes

        # And the fetched bytes are a genuinely valid ZIP/WACZ container.
        with zipfile.ZipFile(io.BytesIO(fetch_resp.content)) as zf:
            assert "datapackage.json" in zf.namelist()
    finally:
        await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", created["id"])
        await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", created["id"])
        await conn.execute("DELETE FROM sites WHERE id = $1", site_row["id"])
        await conn.close()
        minio.client.delete_object(Bucket=minio.bucket_wacz, Key=wacz_key)
        app.dependency_overrides.pop(get_db_connection, None)
