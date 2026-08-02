import json
from typing import Optional, Dict, Any

import asyncpg


async def execute_rag_query(
    conn: asyncpg.Connection,
    question: str,
    municipality_slug: Optional[str] = None,
    top_k: int = 3,
) -> Dict[str, Any]:
    """RAG retrieval is currently a hardcoded keyword-match simulation, not
    real AI - a known, separately-tracked limitation (would need a real
    embedding model + LLM, e.g. Ollama, which isn't running in this
    environment). The trace/feedback persistence below IS real (writes to
    the ai_traces table), independent of that limitation."""
    q_lower = question.lower()

    sources = []
    if "könyvtár" in q_lower or "épület" in q_lower or "székesfehérvár" in q_lower:
        sources.append({
            "snapshot_id": "550e8400-e29b-41d4-a716-446655440091",
            "pid": "fewa:2026:000002",
            "seed_url": "https://vmk.hu/evkonyv-2025",
            "crawl_timestamp": "2026-06-01T12:00:00+02:00",
            "chunk_excerpt": "A Vörösmarty Mihály Könyvtár Székesfehérvár belvárosában működik.",
            "relevance_score": 0.88,
        })
    elif "városháza" in q_lower:
        sources.append({
            "snapshot_id": "550e8400-e29b-41d4-a716-446655440090",
            "pid": "fewa:2026:000001",
            "seed_url": "https://szekesfehervar.hu/hirek/varoshaza-felujitas",
            "crawl_timestamp": "2026-07-15T10:00:00+02:00",
            "chunk_excerpt": "A székesfehérvári Városháza műemléki felújítása 2026-ban folytatódott.",
            "relevance_score": 0.92,
        })

    sources = sources[:top_k]
    confidence_score = max([s["relevance_score"] for s in sources], default=0.3)
    is_sufficient = confidence_score >= 0.6

    if is_sufficient:
        answer = f"Az archívum alapján: {sources[0]['chunk_excerpt']}"
    else:
        answer = "Nincs elegendő bizonyíték az archívumban."

    row = await conn.fetchrow(
        """
        INSERT INTO ai_traces (trace_type, prompt_text, response_text, confidence_score, retrieved_chunks)
        VALUES ('rag_query', $1, $2, $3, $4)
        RETURNING id
        """,
        question, answer, confidence_score, json.dumps(sources),
    )
    trace_id = str(row["id"])

    return {
        "answer": answer,
        "confidence_score": confidence_score,
        "is_sufficient": is_sufficient,
        "sources": sources,
        "warning": "Kísérleti AI-válasz — ellenőrizze az eredeti forrást",
        "trace_id": trace_id,
    }


async def record_rag_feedback(
    conn: asyncpg.Connection, trace_id: str, feedback: str, note: Optional[str] = None
) -> bool:
    try:
        result = await conn.execute(
            "UPDATE ai_traces SET user_feedback = $2, feedback_note = $3 WHERE id = $1",
            trace_id, feedback, note,
        )
    except asyncpg.DataError:
        # Malformed UUID -> "not found" from the caller's perspective, same
        # as a real, well-formed-but-nonexistent trace_id. Anything else
        # (a real DB/connection error) should propagate as a 500, not be
        # swallowed into a misleading 404.
        return False
    return result == "UPDATE 1"
