"""Real, asyncpg-backed CRUD for the admin discovery/quality-approval
workflow — operates on the REAL archived_snapshots lifecycle state machine
already defined in spec/schema.sql (candidate -> approved -> crawling ->
archived -> indexed -> published), enforced by the DB's own
trg_lifecycle_guard trigger. No in-memory dict, no simulation.

Unlike app/crud/sites.py (still in-memory — a separate, tracked gap), every
function here takes a real asyncpg.Connection and does real SQL.
"""

import json
import uuid
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
    requested_depth: int = 2,
    max_pages: int = 25,
) -> Dict[str, Any]:
    """A discovered candidate enters the workflow here — lifecycle_status
    starts at 'candidate', nothing is crawled yet. discovery_metadata (e.g.
    matched locality terms, source search query) is recorded in
    lifecycle_events for later review of why the discovery filter flagged it.

    Regression fix (2026-08-03): this had NO dedup check at all — every call
    unconditionally inserted a new row, so repeated ingests of different
    sub-page URLs on the same domain (site_id) each became their own
    "site" in search results (www.szekesfehervar.hu ended up with 9). A
    site may have at most one snapshot in play — anything short of
    withdrawn/deprecated — at a time; withdraw or let the existing one
    reach a terminal state before ingesting a new seed_url for that site."""
    existing = await conn.fetchrow(
        """
        SELECT id, seed_url, lifecycle_status FROM archived_snapshots
        WHERE site_id = $1 AND lifecycle_status NOT IN ('withdrawn', 'deprecated')
        LIMIT 1
        """,
        site_id,
    )
    if existing:
        raise ValueError(
            f"Ehhez a webhelyhez (site_id={site_id}) már van folyamatban lévő "
            f"jelölt/archívum ({existing['seed_url']}, státusz: {existing['lifecycle_status']}) "
            "— előbb azt kell lezárni (withdrawn/deprecated), mielőtt új URL-t "
            "lehetne ingestálni ugyanerre a webhelyre."
        )

    row = await conn.fetchrow(
        """
        INSERT INTO archived_snapshots
            (tenant_id, site_id, seed_url, dc_title, lifecycle_status, lifecycle_reason, created_by, municipality_id, requested_depth, max_pages)
        VALUES ($1, $2, $3, $4, 'candidate', $5, $6, (SELECT municipality_id FROM sites WHERE id = $2), $7, $8)
        RETURNING id, pid, lifecycle_status, dc_title, seed_url, created_at, requested_depth, max_pages
        """,
        tenant_id, site_id, seed_url, dc_title, discovery_reason, created_by, requested_depth, max_pages,
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


async def update_crawl_progress(
    conn: asyncpg.Connection, snapshot_id: str, pages_crawled: int, current_depth: int,
) -> None:
    await conn.execute(
        "UPDATE archived_snapshots SET pages_crawled = $2, current_depth = $3, updated_at = now() WHERE id = $1",
        snapshot_id, pages_crawled, current_depth,
    )


async def list_stale_approved(conn: asyncpg.Connection, older_than_minutes: int) -> List[Dict[str, Any]]:
    """Approved snapshots whose crawl job never started — either the enqueue
    call failed, or (the 2026-08-02 incident) the job sat in Redis until it
    silently expired during a worker outage. Nothing else notices this;
    app/workers/arq_worker.py's reconcile_stalled_snapshots cron uses this
    to re-enqueue them."""
    rows = await conn.fetch(
        """
        SELECT id, site_id, seed_url
        FROM archived_snapshots
        WHERE lifecycle_status = 'approved'
          AND updated_at < now() - make_interval(mins => $1)
        """,
        older_than_minutes,
    )
    return [dict(r) for r in rows]


async def list_stale_crawling(conn: asyncpg.Connection, older_than_minutes: int) -> List[Dict[str, Any]]:
    """Snapshots stuck in 'crawling' well past a sane duration — the crawl
    job crashed rather than reaching run_crawl_job's own failure return
    (e.g. worker killed mid-job). Same silent-loss failure mode as
    list_stale_approved above."""
    rows = await conn.fetch(
        """
        SELECT id, site_id, seed_url
        FROM archived_snapshots
        WHERE lifecycle_status = 'crawling'
          AND updated_at < now() - make_interval(mins => $1)
        """,
        older_than_minutes,
    )
    return [dict(r) for r in rows]


async def revert_stalled_crawl(conn: asyncpg.Connection, snapshot_id: str, reason: str) -> Dict[str, Any]:
    """crawling -> candidate (a schema-allowed transition): sends a stalled
    crawl back for a curator to knowingly re-approve, rather than the
    reconciler retrying a possibly-broken crawl unattended forever."""
    row = await conn.fetchrow(
        """
        UPDATE archived_snapshots
        SET lifecycle_status = 'candidate', lifecycle_reason = $2
        WHERE id = $1 AND lifecycle_status = 'crawling'
        RETURNING id, lifecycle_status
        """,
        snapshot_id, reason,
    )
    if row is None:
        raise ValueError(f"Snapshot {snapshot_id} not found or not in 'crawling' status.")
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


async def _publish(conn: asyncpg.Connection, snapshot_id: str, reason: str) -> Dict[str, Any]:
    """indexed -> published: the only thing gating public visibility is a
    passing QC score (auto or human-reviewed) — the schema defines no
    further approval gate before 'published', so this always follows
    immediately after a snapshot reaches 'indexed'. See spec/schema.sql's
    valid_transitions and v_published_snapshots (what GET /api/search
    actually queries — app/services/search_service.py)."""
    row = await conn.fetchrow(
        """
        UPDATE archived_snapshots
        SET lifecycle_status = 'published', lifecycle_reason = $2
        WHERE id = $1 AND lifecycle_status = 'indexed'
        RETURNING id, lifecycle_status, qc_score
        """,
        snapshot_id, reason,
    )
    if row is None:
        raise ValueError(f"Snapshot {snapshot_id} not found or not in 'indexed' status.")
    return dict(row)


async def record_qc_result(
    conn: asyncpg.Connection, snapshot_id: str,
    qc_score: int, qc_detail: Dict[str, Any], auto_accept_threshold: int,
) -> Dict[str, Any]:
    """Records the real QA score/detail. If qc_score meets the threshold,
    auto-transitions archived -> indexed -> published (the content was
    already approved at the candidate stage — no second human gate needed
    for a passing score). Below threshold, the row stays 'archived' and
    becomes visible in the quality-review queue for a human decision."""
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
            if row is None:
                raise ValueError(f"Snapshot {snapshot_id} not found.")
            row = await _publish(conn, snapshot_id, "Auto-published after auto-accepted QC")
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
    async with conn.transaction():
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
        if accept:
            row = await _publish(conn, snapshot_id, "Published after human quality-review acceptance")
        return dict(row)


async def withdraw_published_snapshot(
    conn: asyncpg.Connection,
    snapshot_id: str,
    actor_id: str,
    reason: str,
) -> Dict[str, Any]:
    """Withdraws a previously published snapshot by inserting an ARCH-01 release_decisions
    audit row and setting lifecycle_status='withdrawn' within the same transaction."""
    async with conn.transaction():
        snapshot = await conn.fetchrow(
            "SELECT id, wacz_sha256 FROM archived_snapshots WHERE id = $1 AND lifecycle_status = 'published'",
            snapshot_id,
        )
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found or not in 'published' status.")

        artifact_sha256 = snapshot["wacz_sha256"] or "0" * 64
        idempotency_key = f"withdraw-{snapshot_id}-{uuid.uuid4()}"

        await conn.execute(
            """
            INSERT INTO release_decisions
                (snapshot_id, operation, decision_origin, outcome, gate_matrix_hash,
                 artifact_sha256, actor_id, actor_reason,
                 idempotency_key, request_hash, response_hash)
            VALUES ($1::uuid, 'withdraw', 'arch01_gate', 'withdrawn', encode(sha256('arch01_v1'::bytea), 'hex'),
                    $2, $3::uuid, $4,
                    $5, encode(sha256($1::text::bytea), 'hex'), encode(sha256($1::text::bytea), 'hex'))
            """,
            snapshot_id,
            artifact_sha256,
            actor_id,
            reason,
            idempotency_key,
        )

        row = await conn.fetchrow(
            """
            UPDATE archived_snapshots
            SET lifecycle_status = 'withdrawn', lifecycle_reason = $2
            WHERE id = $1
            RETURNING id, lifecycle_status
            """,
            snapshot_id,
            reason,
        )
        return dict(row)

