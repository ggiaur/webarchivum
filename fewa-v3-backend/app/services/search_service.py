"""Real, Postgres-backed public search — queries v_published_snapshots
(spec/schema.sql), the view the schema's own comment says is exactly for
this: "Next.js SSR és API /search végpont használja." Replaces a previous
version of this module that served a hardcoded array of 7 fabricated
snapshot records (fake qc_score, fake seed_url, fake municipality data) to
every visitor — the highest-severity finding of this session (see task
#40), since it sat in the public-facing API, not internal test scaffolding.

Full-text search uses the schema's real Hungarian tsvector/GIN index
(search_vector, weighted dc_title > dc_description/dc_subject > ai_summary
— see update_search_vector() trigger). "hybrid"/"vector" search_type is
honestly degraded to fulltext-only for now: real embeddings
(app/pipeline/embedding.py) are still a separate, tracked gap (hash-based
mock), so there is no real vector index to combine with yet — this module
does not pretend otherwise.
"""

from typing import Any, Dict, List, Optional

import asyncpg


async def execute_hybrid_search(
    conn: asyncpg.Connection,
    q: Optional[str] = None,
    search_type: str = "hybrid",
    municipality_slug: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    q_clean = (q or "").strip()
    offset = (page - 1) * page_size

    where_clauses = ["1=1"]
    params: List[Any] = []

    if q_clean:
        params.append(q_clean)
        where_clauses.append(f"search_vector @@ plainto_tsquery('hungarian', ${len(params)})")
    if municipality_slug:
        params.append(municipality_slug)
        where_clauses.append(f"municipality_slug = ${len(params)}")
    if category:
        # site_category is a Postgres enum (site_category_enum), and ILIKE
        # has no operator against an enum — comparing directly raised
        # "operator does not exist: site_category_enum ~~* unknown" (HTTP
        # 500) for every category, which broke the only navigation path
        # from /collections into the archive. Cast to text to compare.
        # Exact match, not a %wildcard%: the frontend passes the real enum
        # id (see the /collections page), and substring matching across
        # enum values would silently over-match.
        params.append(category)
        where_clauses.append(f"site_category::text = ${len(params)}")

    where_sql = " AND ".join(where_clauses)

    rank_expr = "ts_rank(search_vector, plainto_tsquery('hungarian', $1))" if q_clean else "0.0"

    count_row = await conn.fetchrow(
        f"SELECT COUNT(*) AS total FROM v_published_snapshots WHERE {where_sql}", *params,
    )
    total = count_row["total"]

    params.append(page_size)
    limit_idx = len(params)
    params.append(offset)
    offset_idx = len(params)

    if q_clean:
        # ts_headline's default <b>/</b> highlight markers are used as-is;
        # the frontend currently renders snippet as plain text, so the tags
        # will show literally rather than as bold — a cosmetic frontend
        # follow-up, not a correctness issue here.
        snippet_expr = (
            "ts_headline('hungarian', COALESCE(dc_description, ai_summary, dc_title, ''), "
            "plainto_tsquery('hungarian', $1), 'MaxWords=35, MinWords=15')"
        )
    else:
        snippet_expr = "LEFT(COALESCE(dc_description, ai_summary, ''), 220)"

    rows = await conn.fetch(
        f"""
        SELECT id, pid, dc_title, seed_url, dc_subject,
               municipality_id, municipality_name, municipality_slug,
               crawl_timestamp, qc_score, domain, site_name, site_category,
               site_priority, oszk_status,
               {snippet_expr} AS snippet,
               {rank_expr} AS score
        FROM v_published_snapshots
        WHERE {where_sql}
        ORDER BY score DESC, crawl_timestamp DESC NULLS LAST
        LIMIT ${limit_idx} OFFSET ${offset_idx}
        """,
        *params,
    )

    results = []
    for r in rows:
        item = dict(r)
        item["id"] = str(item["id"])
        item["crawl_timestamp"] = item["crawl_timestamp"].isoformat() if item["crawl_timestamp"] else None
        item["score"] = float(item["score"])
        item["site"] = {"domain": item.pop("domain"), "display_name": item.pop("site_name")}
        item["category"] = item.pop("site_category")
        municipality_id = item.pop("municipality_id")
        municipality_name = item.pop("municipality_name")
        municipality_slug = item.pop("municipality_slug")
        item["municipality"] = (
            {"id": str(municipality_id), "name": municipality_name, "slug": municipality_slug}
            if municipality_id else None
        )
        results.append(item)

    return {
        "results": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "search_type": "fulltext" if search_type in ("hybrid", "vector") else search_type,
        "search_type_requested": search_type,
    }


_DOCUMENT_COLUMNS = """
    s.id, s.pid, s.dc_title, s.dc_description, s.dc_creator, s.dc_publisher,
    s.dc_subject, s.dc_language, s.dc_coverage, s.dc_rights, s.dc_type,
    s.seed_url, s.crawl_timestamp, s.crawl_duration_s, s.qc_score,
    s.ai_summary, s.ai_keywords, s.wacz_minio_path, s.wacz_sha256,
    s.wacz_filesize_bytes, s.wacz_page_count, s.lifecycle_status,
    si.domain, si.display_name AS site_display_name,
    m.name AS municipality_name, m.slug AS municipality_slug
"""


async def get_document_by_id(conn: asyncpg.Connection, doc_id: str, minio_client) -> Optional[Dict[str, Any]]:
    """Only 'published' snapshots are visible publicly — same gate as
    search. Returns a real wacz_url (a presigned MinIO URL) for
    ReplayWeb.page to load directly, or None if no WACZ has been recorded
    yet (should not happen for a published snapshot, but not assumed)."""
    try:
        row = await conn.fetchrow(
            f"""
            SELECT {_DOCUMENT_COLUMNS}
            FROM archived_snapshots s
            JOIN sites si ON si.id = s.site_id
            LEFT JOIN municipalities m ON m.id = s.municipality_id
            WHERE s.id = $1 AND s.lifecycle_status = 'published'
            """,
            doc_id,
        )
    except (ValueError, asyncpg.DataError):
        return None

    if row is None:
        return None

    return _document_row_to_dict(row, minio_client)


async def get_document_by_id_for_curator(conn: asyncpg.Connection, doc_id: str, minio_client) -> Optional[Dict[str, Any]]:
    """Admin-scoped equivalent of get_document_by_id, WITHOUT the
    published-only gate — a curator reviewing the quality-review queue
    needs to preview 'archived'/'indexed' snapshots that aren't public yet
    (that's the whole point of reviewing them before publication).

    Regression fix for 2026-08-02: the quality-review tab's replay link
    pointed at the public get_document_by_id, which always 404s for
    anything not yet published — i.e. every single item ever shown in
    that queue. Curators had no way to actually inspect what they were
    accepting/rejecting."""
    try:
        row = await conn.fetchrow(
            f"""
            SELECT {_DOCUMENT_COLUMNS}
            FROM archived_snapshots s
            JOIN sites si ON si.id = s.site_id
            LEFT JOIN municipalities m ON m.id = s.municipality_id
            WHERE s.id = $1
            """,
            doc_id,
        )
    except (ValueError, asyncpg.DataError):
        return None

    if row is None:
        return None

    return _document_row_to_dict(row, minio_client)


def _document_row_to_dict(row, minio_client) -> Dict[str, Any]:
    doc = dict(row)
    doc["id"] = str(doc["id"])
    doc["crawl_timestamp"] = doc["crawl_timestamp"].isoformat() if doc["crawl_timestamp"] else None
    doc["site"] = {"domain": doc.pop("domain"), "display_name": doc.pop("site_display_name")}
    municipality_name = doc.pop("municipality_name", None)
    municipality_slug = doc.pop("municipality_slug", None)
    doc["municipality"] = {"name": municipality_name, "slug": municipality_slug} if municipality_name else None

    # A same-origin path, NOT a presigned MinIO URL: presigned URLs pointed
    # at MINIO_ENDPOINT (localhost:9002), which a real user's browser can't
    # reach and which is mixed content on an https:// page — replay died
    # with "TypeError: Failed to fetch" (2026-08-02). Served by
    # app/api/v1/search.py::get_wacz (public) and jobs.py's curator route.
    doc["wacz_url"] = f"/api/wacz/{doc['id']}" if doc.get("wacz_minio_path") else None
    return doc
