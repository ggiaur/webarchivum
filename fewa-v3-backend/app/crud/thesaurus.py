"""Real, asyncpg-backed CRUD for the SKOS thesaurus — operates on the real
`skos_concepts` table (spec/schema.sql). Replaces a previous version that
was a pure in-memory dict (two hardcoded fixture concepts, reset on every
process restart).
"""

from typing import Any, Dict, List, Optional, Tuple

import asyncpg

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

_CONCEPT_COLUMNS = """
    c.id, c.tenant_id, c.uri, c.pref_label_hu, c.pref_label_en, c.alt_labels,
    c.definition, c.scope_note, c.notation, c.broader_id, c.is_deprecated,
    c.created_at, c.updated_at,
    b.pref_label_hu AS broader_pref_label_hu
"""


def _slugify(text: str) -> str:
    return text.lower().replace(" ", "-")


async def _row_to_concept(conn: asyncpg.Connection, row: asyncpg.Record) -> Dict[str, Any]:
    concept = dict(row)
    concept["id"] = str(concept["id"])
    concept["tenant_id"] = str(concept["tenant_id"])
    concept["broader_id"] = str(concept["broader_id"]) if concept["broader_id"] else None

    broader_label = concept.pop("broader_pref_label_hu")
    concept["broader"] = (
        {"id": concept["broader_id"], "pref_label_hu": broader_label} if concept["broader_id"] else None
    )

    narrower_rows = await conn.fetch(
        "SELECT id, pref_label_hu FROM skos_concepts WHERE broader_id = $1", concept["id"],
    )
    concept["narrower"] = [{"id": str(r["id"]), "pref_label_hu": r["pref_label_hu"]} for r in narrower_rows]
    return concept


async def get_concept_by_id(conn: asyncpg.Connection, concept_id: str) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow(
        f"""
        SELECT {_CONCEPT_COLUMNS}
        FROM skos_concepts c
        LEFT JOIN skos_concepts b ON b.id = c.broader_id
        WHERE c.id = $1
        """,
        concept_id,
    )
    if row is None:
        return None
    return await _row_to_concept(conn, row)


async def list_concepts(
    conn: asyncpg.Connection,
    q: Optional[str] = None,
    broader_id: Optional[str] = None,
    include_deprecated: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    where_clauses = ["1=1"]
    params: List[Any] = []

    if not include_deprecated:
        where_clauses.append("c.is_deprecated = FALSE")
    if broader_id:
        params.append(broader_id)
        where_clauses.append(f"c.broader_id = ${len(params)}")
    if q:
        params.append(f"%{q}%")
        idx = len(params)
        where_clauses.append(
            f"(c.pref_label_hu ILIKE ${idx} OR c.pref_label_en ILIKE ${idx} "
            f"OR EXISTS (SELECT 1 FROM unnest(c.alt_labels) alt WHERE alt ILIKE ${idx}))"
        )

    where_sql = " AND ".join(where_clauses)

    count_row = await conn.fetchrow(
        f"SELECT COUNT(*) AS total FROM skos_concepts c WHERE {where_sql}", *params,
    )
    total = count_row["total"]

    params.append(page_size)
    limit_idx = len(params)
    params.append((page - 1) * page_size)
    offset_idx = len(params)

    rows = await conn.fetch(
        f"""
        SELECT {_CONCEPT_COLUMNS}
        FROM skos_concepts c
        LEFT JOIN skos_concepts b ON b.id = c.broader_id
        WHERE {where_sql}
        ORDER BY c.pref_label_hu
        LIMIT ${limit_idx} OFFSET ${offset_idx}
        """,
        *params,
    )
    concepts = [await _row_to_concept(conn, r) for r in rows]
    return concepts, total


async def create_concept(
    conn: asyncpg.Connection, data: Dict[str, Any], tenant_id: str = DEFAULT_TENANT_ID,
) -> Dict[str, Any]:
    uri = f"http://fewa.vmk.hu/thesaurus/{_slugify(data['pref_label_hu'])}"
    row = await conn.fetchrow(
        """
        INSERT INTO skos_concepts (
            tenant_id, uri, pref_label_hu, pref_label_en, alt_labels,
            definition, scope_note, notation, broader_id
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id
        """,
        tenant_id, uri, data["pref_label_hu"], data.get("pref_label_en"),
        data.get("alt_labels") or [], data.get("definition"), data.get("scope_note"),
        data.get("notation"), data.get("broader_id"),
    )
    return await get_concept_by_id(conn, str(row["id"]))


_UPDATABLE_FIELDS = [
    "pref_label_hu", "pref_label_en", "alt_labels", "definition",
    "scope_note", "notation", "broader_id", "is_deprecated",
]


async def update_concept(conn: asyncpg.Connection, concept_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = {k: v for k, v in updates.items() if k in _UPDATABLE_FIELDS and v is not None}
    if not fields:
        return await get_concept_by_id(conn, concept_id)

    set_clauses = []
    params: List[Any] = []
    for key, value in fields.items():
        params.append(value)
        set_clauses.append(f"{key} = ${len(params)}")
    params.append(concept_id)

    row = await conn.fetchrow(
        f"UPDATE skos_concepts SET {', '.join(set_clauses)} WHERE id = ${len(params)} RETURNING id",
        *params,
    )
    if row is None:
        return None
    return await get_concept_by_id(conn, concept_id)
