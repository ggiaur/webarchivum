import uuid
import pytest
from app.workers.arq_worker import run_crawl_job, run_enrich_job, run_reembed_job, _JOBS_DB


@pytest.mark.asyncio
async def test_run_crawl_job_execution():
    job_id = uuid.uuid4()
    site_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()

    payload = {
        "job_id": str(job_id),
        "site_id": str(site_id),
        "snapshot_id": str(snapshot_id),
        "seed_url": "https://alba.hu",
        "depth": 3,
        "max_pages": 5000,
        "llm_profile": "balanced",
    }

    res = await run_crawl_job({}, payload)

    assert res["status"] == "completed"
    assert res["job_id"] == str(job_id)
    assert str(job_id) in _JOBS_DB
    assert _JOBS_DB[str(job_id)]["status"] == "completed"


@pytest.mark.asyncio
async def test_run_enrich_job_execution():
    job_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()

    payload = {
        "job_id": str(job_id),
        "snapshot_id": str(snapshot_id),
        "wacz_minio_path": "wacz/2026/07/test.wacz",
        "llm_profile": "balanced",
    }

    res = await run_enrich_job({}, payload)

    assert res["status"] == "completed"
    assert res["qc_score"] == 95
