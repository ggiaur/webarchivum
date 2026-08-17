"""Real, asyncpg-backed CRUD for the admin site-management workflow —
operates on the real `sites` and `crawl_policies` tables (spec/schema.sql).

Replaces a previous version of this module that was a pure in-memory dict
(a single hardcoded "alba.hu" fixture, reset on every process restart) —
the real candidate/QC workflow (app/crud/archive.py) already bypassed it
via get_or_create_site_by_domain; this brings the admin listing/create/
update endpoints (app/api/v1/sites.py) onto the same real data.
"""

from typing import Any, Dict, List, Optional, Tuple

import asyncpg

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

_SITE_COLUMNS = """
    s.id, s.tenant_id, s.domain, s.base_url, s.display_name, s.priority,
    s.category, s.crawl_frequency, s.curator_notes, s.oszk_status,
    s.is_active_collection, s.robots_txt_respect, s.requires_js,
    s.scope_restriction, s.municipality_id, s.last_crawled_at,
    s.rights_holder_name, s.rights_holder_email, s.rights_holder_contact_other, s.permission_status,
    s.created_at, s.updated_at,
    m.name AS municipality_name, m.slug AS municipality_slug,
    m.county AS municipality_county, m.is_active AS municipality_is_active,
    m.sort_order AS municipality_sort_order,
    (SELECT COUNT(*) FROM archived_snapshots a WHERE a.site_id = s.id) AS total_snapshots
"""


def _row_to_site(row: asyncpg.Record) -> Dict[str, Any]:
    site = dict(row)
    site["id"] = str(site["id"])
    site["tenant_id"] = str(site["tenant_id"])
    site["municipality_id"] = str(site["municipality_id"]) if site["municipality_id"] else None

    municipality_name = site.pop("municipality_name")
    municipality_slug = site.pop("municipality_slug")
    municipality_county = site.pop("municipality_county")
    municipality_is_active = site.pop("municipality_is_active")
    municipality_sort_order = site.pop("municipality_sort_order")
    site["municipality"] = (
        {
            "id": site["municipality_id"],
            "name": municipality_name,
            "slug": municipality_slug,
            "county": municipality_county,
            "is_active": municipality_is_active,
            "sort_order": municipality_sort_order,
        }
        if municipality_name else None
    )
    return site


async def _attach_crawl_policies(conn: asyncpg.Connection, site: Dict[str, Any]) -> Dict[str, Any]:
    rows = await conn.fetch(
        "SELECT * FROM crawl_policies WHERE site_id = $1 ORDER BY is_default DESC, created_at ASC",
        site["id"],
    )
    policies = []
    for r in rows:
        p = dict(r)
        p["id"] = str(p["id"])
        p["site_id"] = str(p["site_id"])
        policies.append(p)
    site["crawl_policies"] = policies
    return site


async def get_site_by_id(conn: asyncpg.Connection, site_id: str) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow(
        f"""
        SELECT {_SITE_COLUMNS}
        FROM sites s
        LEFT JOIN municipalities m ON m.id = s.municipality_id
        WHERE s.id = $1
        """,
        site_id,
    )
    if row is None:
        return None
    return await _attach_crawl_policies(conn, _row_to_site(row))


async def get_site_by_domain(conn: asyncpg.Connection, domain: str) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow(
        f"""
        SELECT {_SITE_COLUMNS}
        FROM sites s
        LEFT JOIN municipalities m ON m.id = s.municipality_id
        WHERE lower(s.domain) = lower($1)
        """,
        domain,
    )
    if row is None:
        return None
    return await _attach_crawl_policies(conn, _row_to_site(row))


async def list_sites(
    conn: asyncpg.Connection,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    is_active_collection: Optional[bool] = None,
    municipality_slug: Optional[str] = None,
    oszk_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    where_clauses = ["1=1"]
    params: List[Any] = []

    if priority:
        params.append(priority)
        where_clauses.append(f"s.priority = ${len(params)}")
    if category:
        params.append(category)
        where_clauses.append(f"s.category = ${len(params)}")
    if is_active_collection is not None:
        params.append(is_active_collection)
        where_clauses.append(f"s.is_active_collection = ${len(params)}")
    if municipality_slug:
        params.append(municipality_slug)
        where_clauses.append(f"m.slug = ${len(params)}")
    if oszk_status:
        params.append(oszk_status)
        where_clauses.append(f"s.oszk_status = ${len(params)}")

    where_sql = " AND ".join(where_clauses)

    count_row = await conn.fetchrow(
        f"SELECT COUNT(*) AS total FROM sites s LEFT JOIN municipalities m ON m.id = s.municipality_id WHERE {where_sql}",
        *params,
    )
    total = count_row["total"]

    params.append(page_size)
    limit_idx = len(params)
    params.append((page - 1) * page_size)
    offset_idx = len(params)

    rows = await conn.fetch(
        f"""
        SELECT {_SITE_COLUMNS}
        FROM sites s
        LEFT JOIN municipalities m ON m.id = s.municipality_id
        WHERE {where_sql}
        ORDER BY s.priority, s.domain
        LIMIT ${limit_idx} OFFSET ${offset_idx}
        """,
        *params,
    )
    sites = [await _attach_crawl_policies(conn, _row_to_site(r)) for r in rows]
    return sites, total


async def create_site(
    conn: asyncpg.Connection, data: Dict[str, Any], tenant_id: str = DEFAULT_TENANT_ID,
) -> Dict[str, Any]:
    """Raises ValueError (mapped to 409 by the API layer) on duplicate
    (tenant_id, domain) — enforced by the DB's own real UNIQUE constraint,
    not an application-level pre-check."""
    async with conn.transaction():
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO sites (
                    tenant_id, domain, base_url, display_name, priority, category,
                    crawl_frequency, curator_notes, oszk_status, robots_txt_respect,
                    requires_js, municipality_id,
                    rights_holder_name, rights_holder_email, rights_holder_contact_other, permission_status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id
                """,
                tenant_id, data["domain"], data["base_url"], data.get("display_name") or data["domain"],
                data.get("priority", "medium"), data.get("category", "egyéb"),
                data.get("crawl_frequency", "monthly"), data.get("curator_notes"),
                data.get("oszk_status", "unknown"), data.get("robots_txt_respect", True),
                data.get("requires_js", False), data.get("municipality_id"),
                data.get("rights_holder_name"), data.get("rights_holder_email"),
                data.get("rights_holder_contact_other"), data.get("permission_status", "nincs_megkeresve"),
            )
        except asyncpg.UniqueViolationError:
            raise ValueError(f"Domain {data['domain']} is already registered.")

        site_id = row["id"]
        await conn.execute(
            "INSERT INTO crawl_policies (site_id, name, is_default) VALUES ($1, 'default', TRUE)",
            site_id,
        )

    return await get_site_by_id(conn, str(site_id))


_UPDATABLE_FIELDS = [
    "display_name", "priority", "category", "crawl_frequency", "municipality_id",
    "curator_notes", "oszk_status", "is_active_collection", "robots_txt_respect", "requires_js",
    "rights_holder_name", "rights_holder_email", "rights_holder_contact_other", "permission_status",
]


async def update_site(conn: asyncpg.Connection, site_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = {k: v for k, v in updates.items() if k in _UPDATABLE_FIELDS and v is not None}
    if not fields:
        return await get_site_by_id(conn, site_id)

    set_clauses = []
    params: List[Any] = []
    for key, value in fields.items():
        params.append(value)
        set_clauses.append(f"{key} = ${len(params)}")
    params.append(site_id)

    row = await conn.fetchrow(
        f"UPDATE sites SET {', '.join(set_clauses)} WHERE id = ${len(params)} RETURNING id",
        *params,
    )
    if row is None:
        return None
    return await get_site_by_id(conn, site_id)
