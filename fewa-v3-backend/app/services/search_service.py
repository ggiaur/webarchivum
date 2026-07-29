import time
from typing import Optional, List, Dict, Any

# Mock published snapshots database for Search & RAG testing
_SEARCH_SNAPSHOTS_DB = [
    {
        "id": "550e8400-e29b-41d4-a716-446655440090",
        "pid": "fewa:2026:000001",
        "dc_title": "Székesfehérvár MJV Polgármesteri Hivatal Hírei",
        "dc_description": "Városháza felújítási munkálatai és közgyűlési határozatok.",
        "dc_subject": ["önkormányzat", "helyi politika", "városfejlesztés"],
        "snippet": "Elkezdődött a székesfehérvári Városháza műemléki épületének felújítása és digitális archívumának bővítése.",
        "seed_url": "https://szekesfehervar.hu/hirek/varoshaza-felujitas",
        "crawl_timestamp": "2026-07-15T10:00:00+02:00",
        "qc_score": 98,
        "category": "Önkormányzatok & Hivatalok",
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
        "id": "550e8400-e29b-41d4-a716-446655440092",
        "pid": "fewa:2026:000003",
        "dc_title": "Dunaújváros MJV Önkormányzat Hivatalos Közleményei",
        "dc_description": "Helyi rendeletek, városüzemeltetési hírek és közgyűlési döntések.",
        "dc_subject": ["önkormányzat", "közigazgatás", "Dunaújváros"],
        "snippet": "Dunaújváros Megyei Jogú Város Közgyűlése elfogadta a 2026. évi fejlesztési és energetikai stratégiát.",
        "seed_url": "https://dunaujvaros.hu/kozlemenyek/strategia-2026",
        "crawl_timestamp": "2026-07-10T14:30:00+02:00",
        "qc_score": 96,
        "category": "Önkormányzatok & Hivatalok",
        "municipality_slug": "dunauvaros",
        "municipality": {
            "id": "muni-002-dunauvaros",
            "name": "Dunaújváros",
            "slug": "dunauvaros",
            "county": "Fejér",
            "is_active": True,
            "sort_order": 20,
        },
        "site": {
            "domain": "dunaujvaros.hu",
            "display_name": "Dunaújváros Önkormányzati Portál",
        },
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440093",
        "pid": "fewa:2026:000004",
        "dc_title": "Mór Város Önkormányzat Hivatalos Lapja és Hírei",
        "dc_description": "Móri borvidék fejlesztési programok és helyhatósági döntések.",
        "dc_subject": ["önkormányzat", "Mór", "helyi hírek"],
        "snippet": "Megnyílt a Móri Borvidék kulturális és turisztikai központjának megújult felülete.",
        "seed_url": "https://mor.hu/hirek/borvidek-központ",
        "crawl_timestamp": "2026-07-08T09:15:00+02:00",
        "qc_score": 94,
        "category": "Önkormányzatok & Hivatalok",
        "municipality_slug": "mor",
        "municipality": {
            "id": "muni-003-mor",
            "name": "Mór",
            "slug": "mor",
            "county": "Fejér",
            "is_active": True,
            "sort_order": 30,
        },
        "site": {
            "domain": "mor.hu",
            "display_name": "Mór Város Portál",
        },
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440094",
        "pid": "fewa:2026:000005",
        "dc_title": "FEOL — Fejér Megyei Hírportál Archívum",
        "dc_description": "Fejér vármegyei napi hírek, tudósítások, gazdasági és sporthírek.",
        "dc_subject": ["sajtó", "média", "hírek", "Fejér vármegye"],
        "snippet": "Átfogó összefoglaló Fejér vármegye elmúlt évtizedének legfontosabb gazdasági és kulturális eseményeiről.",
        "seed_url": "https://feol.hu/helyi-ertekek-fejer-megye",
        "crawl_timestamp": "2026-07-01T11:00:00+02:00",
        "qc_score": 97,
        "category": "Helyi Sajtó & Média",
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
            "domain": "feol.hu",
            "display_name": "FEOL Megyei Hírportál",
        },
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440095",
        "pid": "fewa:2026:000006",
        "dc_title": "Dunaújvárosi Hírlap Digitális Lapszámok",
        "dc_description": "Dunaújváros és kistérsége független hírei, riportok és archív cikkek.",
        "dc_subject": ["sajtó", "média", "Dunaújváros"],
        "snippet": "Megjelent a Dunaújvárosi Hírlap jubileumi különszáma a város ipartörténetéről.",
        "seed_url": "https://duol.hu/dunauvaros-ipartortenet",
        "crawl_timestamp": "2026-06-20T16:00:00+02:00",
        "qc_score": 93,
        "category": "Helyi Sajtó & Média",
        "municipality_slug": "dunauvaros",
        "municipality": {
            "id": "muni-002-dunauvaros",
            "name": "Dunaújváros",
            "slug": "dunauvaros",
            "county": "Fejér",
            "is_active": True,
            "sort_order": 20,
        },
        "site": {
            "domain": "duol.hu",
            "display_name": "DUOL Dunaújvárosi Hírportál",
        },
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440091",
        "pid": "fewa:2026:000002",
        "dc_title": "Vörösmarty Mihály Könyvtár Évkönyv 2025",
        "dc_description": "Könyvtári statisztikák, helytörténeti gyűjtemények és kiadványok.",
        "dc_subject": ["kulturális", "könyvtár", "helytörténet"],
        "snippet": "A Vörösmarty Mihály Könyvtár digitalizálta a Fejér Megyei Hírlap és a helyi sajtó teljes archívumát.",
        "seed_url": "https://vmk.hu/evkonyv-2025",
        "crawl_timestamp": "2026-06-01T12:00:00+02:00",
        "qc_score": 95,
        "category": "Kulturális & Könyvtári Örökség",
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
    {
        "id": "550e8400-e29b-41d4-a716-446655440096",
        "pid": "fewa:2026:000007",
        "dc_title": "Szent István Király Múzeum Digitális Kiállítás",
        "dc_description": "Régészeti, néprajzi és képzőművészeti gyűjtemények digitális katalógusa.",
        "dc_subject": ["kulturális", "múzeum", "örökség", "Székesfehérvár"],
        "snippet": "Online böngészhetővé vált a Szent István Király Múzeum középkori lapidáriuma és коронаciós gyűjteménye.",
        "seed_url": "https://szikm.hu/digitalis-lapidarium",
        "crawl_timestamp": "2026-05-18T10:00:00+02:00",
        "qc_score": 99,
        "category": "Kulturális & Könyvtári Örökség",
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
            "domain": "szikm.hu",
            "display_name": "Szent István Király Múzeum",
        },
    },
]


def execute_hybrid_search(
    q: Optional[str] = None,
    search_type: str = "hybrid",
    municipality_slug: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    start_time = time.time()
    q_lower = (q or "").strip().lower()
    cat_lower = (category or "").strip().lower()

    filtered = []
    for s in _SEARCH_SNAPSHOTS_DB:
        if municipality_slug and s.get("municipality_slug") != municipality_slug:
            continue

        # Check Category Filter
        if cat_lower:
            item_cat = (s.get("category") or "").lower()
            dc_subj = [subj.lower() for subj in s.get("dc_subject", [])]
            cat_words = [w for w in cat_lower.replace("&", " ").split() if len(w) > 2]
            cat_match = (
                cat_lower in item_cat
                or any(w in item_cat for w in cat_words)
                or any(w in s["dc_title"].lower() for w in cat_words)
                or any(w in subj for w in cat_words for subj in dc_subj)
            )
            if not cat_match:
                continue

        if not q_lower:
            item = dict(s)
            item["score"] = 1.0
            filtered.append(item)
        else:
            # Check keyword match in title, description, snippet or subjects
            matched = (
                q_lower in s["dc_title"].lower()
                or q_lower in s["dc_description"].lower()
                or q_lower in s["snippet"].lower()
                or any(q_lower in subj.lower() for subj in s["dc_subject"])
            )

            if matched or len(q_lower) >= 2 or cat_lower:
                score = 0.95 if matched else 0.75
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


def get_document_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    for s in _SEARCH_SNAPSHOTS_DB:
        if s["id"] == doc_id:
            res = dict(s)
            res.setdefault("dc_creator", "Fejér Vármegyei Könyvtári Archívum")
            res.setdefault("dc_publisher", "Vörösmarty Mihály Könyvtár")
            res.setdefault("ai_summary", "A megőrzött digitális állomány automatikusan elemzett kivonata.")
            res.setdefault("ai_keywords", ["Fejér vármegye", "archívum", "WACZ"])
            res.setdefault("wacz_filesize_bytes", 4520100)
            res.setdefault("wacz_page_count", 14)
            return res
    return None
