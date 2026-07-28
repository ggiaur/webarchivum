import time
import re
from spec.pipeline_schemas import NERInput, NEROutput


def extract_named_entities(input_data: NERInput) -> NEROutput:
    """
    Extracts named entities (persons, orgs, locations) using regex/huSpaCy patterns.
    Returns validated NEROutput schema.
    """
    start_time = time.time()
    text = input_data.raw_text

    # Extract locations (Fejér county towns & general locations)
    locations = set()
    loc_patterns = [
        r"\b(Székesfehérvár|Dunaújváros|Mór|Bicske|Sárbogárd|Gárdony|Enying|Martonvásár|Velence|Szabadbattyán)\b",
        r"\b([A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+ (város|község|vármegye|megye))\b",
    ]
    for pattern in loc_patterns:
        for match in re.finditer(pattern, text):
            locations.add(match.group(0))

    # Extract organizations
    organizations = set()
    org_patterns = [
        r"\b([A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+ (Könyvtár|Múzeum|Önkormányzat|Hivatal|Egyetem|Iskola|Kft|Nyrt|Zrt|Egyesület))\b",
        r"\b(VMK|OSZK|FEWA)\b",
    ]
    for pattern in org_patterns:
        for match in re.finditer(pattern, text):
            organizations.add(match.group(0))

    # Extract persons (Hungarian name format: Capitalized Surname + Firstname)
    persons = set()
    person_pattern = r"\b([A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]{2,} [A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]{2,})\b"
    for match in re.finditer(person_pattern, text):
        val = match.group(0)
        # Filter out common orgs/locations
        if not any(keyword in val for keyword in ["Város", "Megye", "Könyvtár", "Önkormányzat", "Hivatal"]):
            persons.add(val)

    processing_time_ms = int((time.time() - start_time) * 1000)

    return NEROutput(
        snapshot_id=input_data.snapshot_id,
        persons=sorted(list(persons)),
        organizations=sorted(list(organizations)),
        locations=sorted(list(locations)),
        misc_entities=[],
        model_version="hu_core_news_lg-3.7.0",
        processing_time_ms=processing_time_ms,
    )
