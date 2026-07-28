import time
from typing import Optional, List, Dict, Any

# Mock published snapshots database for Search & RAG testing
_SEARCH_SNAPSHOTS_DB = [
    {
        "id": "550e8400-e29b-41d4-a716-446655440090",
        "pid": "fewa:2026:000001",
        "dc_title": "Székesfehérvár MJV Polgármesteri Hivatal Hírei",
        "dc_description": "Városháza felújítási munkálatai és közgyűlési határozatok.",
        "dc_subject": ["helyi politika", "városfejlesztés"],
        "snippet": "Elkezdődött a székesfehérvári Városháza műemléki épületének felújítása.",
        "seed_url": "https://szekesfehervar.hu/hirek/varoshaza-felujitas",
        "crawl_timestamp": "2026-07-15T10:00:00+02:00",
        "qc_score": 98,
        "municipality_slug": "szekesfehervar",
        "municipality": {
            "id": "muni-001-szekesfehervar",
            "name": "Székesfehérvár",
            "slug": "szekesfehervar",
            "county": "Fejér",
            "is_active": True,
            "sort_order": 10,
        },
        "site": {
            "domain": "szekesfehervar.hu",
            "display_name": "Székesfehérvár Város Portál",
        },
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440091",
        "pid": "fewa:2026:000002",
        "dc_title": "Vörösmarty Mihály Könyvtár Évkönyv 2025",
        "dc_description": "Könyvtári statisztikák, helytörténeti gyűjtemények és kiadványok.",
        "dc_subject": ["könyvtár", "helytörténet"],
        "snippet": "A Vörösmarty Mihály Könyvtár digitalizálta a Fejér Megyei Hírlap teljes archívumát.",
        "seed_url": "https://vmk.hu/evkonyv-2025",
        "crawl_timestamp": "2026-06-01T12:00:00+02:00",
        "qc_score": 95,
        "municipality_slug": "szekesfehervar",
        "municipality": {
            "id": "muni-001-szekesfehervar",
            "name": "Székesfehérvár",
            "slug": "szekesfehervar",
            "county": "Fejér",
            "is_active": True,
            "sort_order": 10,
        },
        "site": {
            "domain": "vmk.hu",
            "display_name": "Vörösmarty Mihály Könyvtár",
        },
    },
]


def execute_hybrid_search(
    q: str,
    search_type: str = "hybrid",
    municipality_slug: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    start_time = time.time()
    q_lower = q.lower()

    filtered = []
    for s in _SEARCH_SNAPSHOTS_DB:
        if municipality_slug and s.get("municipality_slug") != municipality_slug:
            continue

        # Check keyword match in title, description, snippet or subjects
        matched = (
            q_lower in s["dc_title"].lower()
            or q_lower in s["dc_description"].lower()
            or q_lower in s["snippet"].lower()
            or any(q_lower in subj.lower() for subj in s["dc_subject"])
        )

        if matched or len(q) >= 2:
            score = 0.95 if matched else 0.45
            item = dict(s)
            item["score"] = score
            filtered.append(item)

    filtered.sort(key=lambda x: x["score"], reverse=True)
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    query_time_ms = int((time.time() - start_time) * 1000)

    return {
        "results": filtered[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "search_type": search_type,
        "query_time_ms": max(1, query_time_ms),
    }
