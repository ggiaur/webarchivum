import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# In-memory store for SKOS concepts (for CRUD service & API testing)
_SKOS_DB: Dict[str, Dict[str, Any]] = {
    "concept-001-helyi-politika": {
        "id": "concept-001-helyi-politika",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "uri": "http://fewa.vmk.hu/thesaurus/helyi-politika",
        "pref_label_hu": "helyi politika",
        "pref_label_en": "local politics",
        "alt_labels": ["önkormányzati politika", "helyhatósági ügyek"],
        "definition": "Fejér vármegyei önkormányzati és helyi politikai témák.",
        "scope_note": "Magában foglalja a közgyűlési határozatokat és helyi választásokat.",
        "notation": "HE-001",
        "broader_id": None,
        "broader": None,
        "narrower": [],
        "is_deprecated": False,
        "created_at": "2026-01-15T10:00:00+02:00",
        "updated_at": "2026-01-15T10:00:00+02:00",
    },
    "concept-002-helyi-valasztasok": {
        "id": "concept-002-helyi-valasztasok",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "uri": "http://fewa.vmk.hu/thesaurus/helyi-valasztasok",
        "pref_label_hu": "helyi választások",
        "pref_label_en": "local elections",
        "alt_labels": ["önkormányzati választás"],
        "definition": "Helyi és nemzetiségi önkormányzati választási kampányok és eredmények.",
        "scope_note": None,
        "notation": "HE-002",
        "broader_id": "concept-001-helyi-politika",
        "broader": {"id": "concept-001-helyi-politika", "pref_label_hu": "helyi politika"},
        "narrower": [],
        "is_deprecated": False,
        "created_at": "2026-01-16T10:00:00+02:00",
        "updated_at": "2026-01-16T10:00:00+02:00",
    },
}


def get_concept_by_id(concept_id: str) -> Optional[Dict[str, Any]]:
    return _SKOS_DB.get(concept_id)


def list_concepts(
    q: Optional[str] = None,
    broader_id: Optional[str] = None,
    include_deprecated: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[List[Dict[str, Any]], int]:
    results = list(_SKOS_DB.values())

    if not include_deprecated:
        results = [c for c in results if not c["is_deprecated"]]

    if broader_id:
        results = [c for c in results if c.get("broader_id") == broader_id]

    if q:
        query_lower = q.lower()

        def matches(c):
            if query_lower in c["pref_label_hu"].lower():
                return True
            if c.get("pref_label_en") and query_lower in c["pref_label_en"].lower():
                return True
            if c.get("alt_labels"):
                for alt in c["alt_labels"]:
                    if query_lower in alt.lower():
                        return True
            return False

        results = [c for c in results if matches(c)]

    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    return results[start:end], total


def create_concept(data: Dict[str, Any], tenant_id: str = "00000000-0000-0000-0000-000000000001") -> Dict[str, Any]:
    concept_id = str(uuid.uuid4())
    slug = data["pref_label_hu"].lower().replace(" ", "-")
    uri = f"http://fewa.vmk.hu/thesaurus/{slug}"
    now_iso = datetime.now(timezone.utc).isoformat()

    broader_obj = None
    if data.get("broader_id"):
        parent = get_concept_by_id(data["broader_id"])
        if parent:
            broader_obj = {"id": parent["id"], "pref_label_hu": parent["pref_label_hu"]}

    record = {
        "id": concept_id,
        "tenant_id": tenant_id,
        "uri": uri,
        "pref_label_hu": data["pref_label_hu"],
        "pref_label_en": data.get("pref_label_en"),
        "alt_labels": data.get("alt_labels") or [],
        "definition": data.get("definition"),
        "scope_note": data.get("scope_note"),
        "notation": data.get("notation"),
        "broader_id": data.get("broader_id"),
        "broader": broader_obj,
        "narrower": [],
        "is_deprecated": False,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    _SKOS_DB[concept_id] = record
    return record


def update_concept(concept_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    concept = _SKOS_DB.get(concept_id)
    if not concept:
        return None

    for key, val in updates.items():
        if val is not None and key in concept:
            concept[key] = val

    if "broader_id" in updates and updates["broader_id"]:
        parent = get_concept_by_id(updates["broader_id"])
        if parent:
            concept["broader"] = {"id": parent["id"], "pref_label_hu": parent["pref_label_hu"]}

    concept["updated_at"] = datetime.now(timezone.utc).isoformat()
    _SKOS_DB[concept_id] = concept
    return concept
