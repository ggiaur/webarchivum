import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# In-memory store for sites (for CRUD service & API testing; production connects via asyncpg DDL)
_SITES_DB: Dict[str, Dict[str, Any]] = {
    "550e8400-e29b-41d4-a716-446655440001": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "domain": "alba.hu",
        "base_url": "https://alba.hu",
        "display_name": "Alba Regia Portál",
        "priority": "high",
        "category": "közintézmény",
        "crawl_frequency": "weekly",
        "curator_notes": "Főoldal és hírek archiválása",
        "oszk_status": "no",
        "is_active_collection": True,
        "robots_txt_respect": True,
        "requires_js": False,
        "scope_restriction": None,
        "municipality_id": "muni-001-szekesfehervar",
        "municipality": {
            "id": "muni-001-szekesfehervar",
            "name": "Székesfehérvár",
            "slug": "szekesfehervar",
            "county": "Fejér",
            "is_active": True,
            "sort_order": 10,
        },
        "total_snapshots": 12,
        "last_crawled_at": "2026-07-20T02:00:00+02:00",
        "crawl_policies": [
            {
                "id": "policy-001",
                "site_id": "550e8400-e29b-41d4-a716-446655440001",
                "name": "default",
                "depth": 3,
                "max_pages": 5000,
                "page_limit": 500,
                "cron_schedule": "0 2 * * 0",
                "llm_profile": "balanced",
                "include_patterns": ["/hirek/*"],
                "exclude_patterns": ["/admin/*"],
                "is_active": True,
            }
        ],
        "created_at": "2026-01-10T10:00:00+02:00",
        "updated_at": "2026-07-20T02:00:00+02:00",
    }
}


def get_site_by_id(site_id: str) -> Optional[Dict[str, Any]]:
    return _SITES_DB.get(site_id)


def get_site_by_domain(domain: str) -> Optional[Dict[str, Any]]:
    return next((s for s in _SITES_DB.values() if s["domain"].lower() == domain.lower()), None)


def list_sites(
    priority: Optional[str] = None,
    category: Optional[str] = None,
    is_active_collection: Optional[bool] = None,
    municipality_slug: Optional[str] = None,
    oszk_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[List[Dict[str, Any]], int]:
    results = list(_SITES_DB.values())

    if priority:
        results = [s for s in results if s["priority"] == priority]
    if category:
        results = [s for s in results if s["category"] == category]
    if is_active_collection is not None:
        results = [s for s in results if s["is_active_collection"] == is_active_collection]
    if municipality_slug:
        results = [
            s for s in results
            if s.get("municipality") and s["municipality"].get("slug") == municipality_slug
        ]
    if oszk_status:
        results = [s for s in results if s["oszk_status"] == oszk_status]

    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    return results[start:end], total


def create_site(data: Dict[str, Any], tenant_id: str = "00000000-0000-0000-0000-000000000001") -> Dict[str, Any]:
    if get_site_by_domain(data["domain"]):
        raise ValueError(f"Domain {data['domain']} is already registered.")

    site_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    site_record = {
        "id": site_id,
        "tenant_id": tenant_id,
        "domain": data["domain"],
        "base_url": data["base_url"],
        "display_name": data.get("display_name") or data["domain"],
        "priority": data.get("priority", "medium"),
        "category": data.get("category", "egyéb"),
        "crawl_frequency": data.get("crawl_frequency", "monthly"),
        "curator_notes": data.get("curator_notes"),
        "oszk_status": data.get("oszk_status", "unknown"),
        "is_active_collection": True,
        "robots_txt_respect": data.get("robots_txt_respect", True),
        "requires_js": data.get("requires_js", False),
        "scope_restriction": None,
        "municipality_id": data.get("municipality_id"),
        "municipality": None,
        "total_snapshots": 0,
        "last_crawled_at": None,
        "crawl_policies": [
            {
                "id": str(uuid.uuid4()),
                "site_id": site_id,
                "name": "default",
                "depth": 3,
                "max_pages": 5000,
                "page_limit": 500,
                "cron_schedule": "0 2 * * 0",
                "llm_profile": "balanced",
                "include_patterns": None,
                "exclude_patterns": None,
                "is_active": True,
            }
        ],
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    _SITES_DB[site_id] = site_record
    return site_record


def update_site(site_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    site = _SITES_DB.get(site_id)
    if not site:
        return None

    for key, value in updates.items():
        if value is not None and key in site:
            site[key] = value

    site["updated_at"] = datetime.now(timezone.utc).isoformat()
    _SITES_DB[site_id] = site
    return site
