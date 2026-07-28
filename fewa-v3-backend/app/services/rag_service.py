import uuid
from typing import Optional, List, Dict, Any

# Mock trace storage
_AI_TRACES_DB: Dict[str, Dict[str, Any]] = {}


def execute_rag_query(
    question: str,
    municipality_slug: Optional[str] = None,
    top_k: int = 3,
) -> Dict[str, Any]:
    trace_id = str(uuid.uuid4())
    q_lower = question.lower()

    # RAG Retrieval simulation (top-k)
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

    trace_entry = {
        "trace_id": trace_id,
        "prompt_text": question,
        "answer": answer,
        "confidence_score": confidence_score,
        "is_sufficient": is_sufficient,
        "sources": sources,
    }
    _AI_TRACES_DB[trace_id] = trace_entry

    return {
        "answer": answer,
        "confidence_score": confidence_score,
        "is_sufficient": is_sufficient,
        "sources": sources,
        "warning": "Kísérleti AI-válasz — ellenőrizze az eredeti forrást",
        "trace_id": trace_id,
    }


def record_rag_feedback(trace_id: str, feedback: str, note: Optional[str] = None) -> bool:
    trace = _AI_TRACES_DB.get(trace_id)
    if not trace:
        return False
    trace["user_feedback"] = feedback
    trace["feedback_note"] = note
    return True
