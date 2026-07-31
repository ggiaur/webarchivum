"""Real, asyncpg-backed CRUD for the admin discovery/quality-approval
workflow — operates on the REAL archived_snapshots lifecycle state machine
already defined in spec/schema.sql (candidate -> approved -> crawling ->
archived -> indexed -> published), enforced by the DB's own
trg_lifecycle_guard trigger. No in-memory dict, no simulation.

Unlike app/crud/sites.py (still in-memory — a separate, tracked gap), every
function here takes a real asyncpg.Connection and does real SQL.
"""

import json
from typing import Any, Dict, List, Optional

import asyncpg

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def get_or_create_site_by_domain(
    conn: asyncpg.Connection,
    domain: str,
    base_url: str,
    display_name: Optional[str] = None,
    tenant_id: str = DEFAULT_TENANT_ID,
) -> Dict[str, Any]:
    """Real, minimal site resolution against the actual `sites` table —
    NOT the in-memory app/crud/sites.py (that module backs the older
    /api/v1/sites admin-listing endpoint and remains a separate, tracked
    gap; see commit 85ff6be). The new discovery -> candidate -> QC workflow
    needs a real sites.id to satisfy archived_snapshots' NOT NULL FK, so it
    resolves/creates one directly here rather than depending on that
    in-memory module. (tenant_id, domain) is unique in the schema, so this
    is idempotent."""
    row = await conn.fetchrow(
        """
        INSERT INTO sites (tenant_id, domain, base_url, display_name)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (tenant_id, domain) DO UPDATE SET domain = EXCLUDED.domain
        RETURNING id, domain, base_url, display_name
        """,
        tenant_id, domain, base_url, display_name or domain,
    )
    return dict(row)


async def create_candidate_snapshot(
    conn: asyncpg.Connection,
    site_id: str,
    seed_url: str,
    dc_title: str,
    discovery_reason: str,
    discovery_metadata: Dict[str, Any],
    created_by: Optional[str] = None,
    tenant_id: str = DEFAULT_TENANT_ID,
) -> Dict[str, Any]:
    """A discovered candidate enters the workflow here — lifecycle_status
    starts at 'candidate', nothing is crawled yet. discovery_metadata (e.g.
    matched locality terms, source search query) is recorded in
    lifecycle_events for later review of why the discovery filter flagged it."""
    row = await conn.fetchrow(
        """
        INSERT INTO archived_snapshots
            (tenant_id, site_id, seed_url, dc_title, lifecycle_status, lifecycle_reason, created_by)
        VALUES ($1, $2, $3, $4, 'candidate', $5, $6)
        RETURNING id, pid, lifecycle_status, dc_title, seed_url, created_at
        """,
        tenant_id, site_id, seed_url, dc_title, discovery_reason, created_by,
    )
    # trg_lifecycle_guard only fires on UPDATE OF lifecycle_status, not INSERT —
    # log the initial candidate status manually so the audit trail is complete
    # from the very first event, not just from the first transition onward.
    await conn.execute(
        """
        INSERT INTO lifecycle_events (snapshot_id, from_status, to_status, triggered_by, reason, metadata)
        VALUES ($1, NULL, 'candidate', $2, $3, $4)
        """,
        row["id"], created_by, discovery_reason, json.dumps(discovery_metadata),
    )
    return dict(row)


async def list_candidate_queue(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    rows = await conn.fetch("SELECT * FROM v_admin_queue WHERE lifecycle_status = 'candidate'")
    return [dict(r) for r in rows]


async def approve_candidate(
    conn: asyncpg.Connection, snapshot_id: str, user_id: Optional[str],
    reason: str = "Approved by curator",
) -> Dict[str, Any]:
    row = await conn.fetchrow(
        """
        UPDATE archived_snapshots
        SET lifecycle_status = 'approved', lifecycle_reason = $2, approved_by = $3
        WHERE id = $1 AND lifecycle_status = 'candidate'
        RETURNING id, lifecycle_status
        """,
        snapshot_id, reason, user_id,
    )
    if row is None:
        raise ValueError(f"Snapshot {snapshot_id} not found or not in 'candidate' status.")
    return dict(row)


async def reject_candidate(
    conn: asyncpg.Connection, snapshot_id: str, reason: str,
) -> Dict[str, Any]:
    row = await conn.fetchrow(
        """
        UPDATE archived_snapshots
        SET lifecycle_status = 'withdrawn', lifecycle_reason = $2
        WHERE id = $1 AND lifecycle_status = 'candidate'
        RETURNING id, lifecycle_status
        """,
        snapshot_id, reason,
    )
    if row is None:
        raise ValueError(f"Snapshot {snapshot_id} not found or not in 'candidate' status.")
    return dict(row)


async def mark_crawling(conn: asyncpg.Connection, snapshot_id: str) -> Dict[str, Any]:
    row = await conn.fetchrow(
        """
        UPDATE archived_snapshots SET lifecycle_status = 'crawling'
        WHERE id = $1 AND lifecycle_status = 'approved'
        RETURNING id, lifecycle_status
        """,
        snapshot_id,
    )
    if row is None:
        raise ValueError(f"Snapshot {snapshot_id} not found or not in 'approved' status.")
    return dict(row)


async def record_crawl_result(
    conn: asyncpg.Connection, snapshot_id: str,
    wacz_minio_path: str, wacz_sha256: Optional[str], wacz_filesize_bytes: Optional[int],
) -> Dict[str, Any]:
    row = await conn.fetchrow(
        """
        UPDATE archived_snapshots
        SET lifecycle_status = 'archived', wacz_minio_path = $2, wacz_sha256 = $3,
            wacz_filesize_bytes = $4, crawl_timestamp = now()
        WHERE id = $1 AND lifecycle_status = 'crawling'
        RETURNING id, lifecycle_status
        """,
        snapshot_id, wacz_minio_path, wacz_sha256, wacz_filesize_bytes,
    )
    if row is None:
        raise ValueError(f"Snapshot {snapshot_id} not found or not in 'crawling' status.")
    return dict(row)


async def record_qc_result(
    conn: asyncpg.Connection, snapshot_id: str,
    qc_score: int, qc_detail: Dict[str, Any], auto_accept_threshold: int,
) -> Dict[str, Any]:
    """Records the real QA score/detail. If qc_score meets the threshold,
    auto-transitions archived -> indexed (the content was already approved
    at the candidate stage — no second human gate needed for a passing
    score). Below threshold, the row stays 'archived' and becomes visible
    in the quality-review queue for a human decision."""
    async with conn.transaction():
        await conn.execute(
            "UPDATE archived_snapshots SET qc_score = $2, qc_detail = $3 WHERE id = $1",
            snapshot_id, qc_score, json.dumps(qc_detail),
        )
        if qc_score >= auto_accept_threshold:
            row = await conn.fetchrow(
                """
                UPDATE archived_snapshots
                SET lifecycle_status = 'indexed',
                    lifecycle_reason = $2
                WHERE id = $1 AND lifecycle_status = 'archived'
                RETURNING id, lifecycle_status, qc_score
                """,
                snapshot_id, f"Auto-accepted: qc_score {qc_score} >= threshold {auto_accept_threshold}",
            )
        else:
            row = await conn.fetchrow(
                "SELECT id, lifecycle_status, qc_score FROM archived_snapshots WHERE id = $1",
                snapshot_id,
            )
        if row is None:
            raise ValueError(f"Snapshot {snapshot_id} not found.")
        return dict(row)


async def list_quality_review_queue(conn: asyncpg.Connection, threshold: int) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT id, pid, dc_title, seed_url, qc_score, qc_detail, created_at
        FROM archived_snapshots
        WHERE lifecycle_status = 'archived' AND (qc_score IS NULL OR qc_score < $1)
        ORDER BY created_at ASC
        """,
        threshold,
    )
    return [dict(r) for r in rows]


async def decide_quality_review(
    conn: asyncpg.Connection, snapshot_id: str, accept: bool,
    user_id: Optional[str], reason: str,
) -> Dict[str, Any]:
    """Human decision on a below-threshold archive: accept anyway (->
    indexed) or send back for reconsideration (-> candidate, matching the
    DB's own allowed transition archived -> candidate — 'withdrawn' isn't a
    direct option from 'archived', so a hard reject goes through candidate
    first, same path a human curator would use to withdraw it later)."""
    new_status = "indexed" if accept else "candidate"
    row = await conn.fetchrow(
        """
        UPDATE archived_snapshots
        SET lifecycle_status = $2, lifecycle_reason = $3, approved_by = $4
        WHERE id = $1 AND lifecycle_status = 'archived'
        RETURNING id, lifecycle_status
        """,
        snapshot_id, new_status, reason, user_id,
    )
    if row is None:
        raise ValueError(f"Snapshot {snapshot_id} not found or not in 'archived' status.")
    return dict(row)
