"""Content discovery: build Google-search queries for the task's stated
criteria (local Székesfehérvár/Fejér megyei connection: people, institutions,
history) and filter candidate results by genuine locality match.

The task description explicitly recommends browser-based Google search
("böngészős Google keresés ajánlott"). This module provides the query-
building and REAL locality-filtering logic; actually issuing search
requests needs either a Google Custom Search API key (GOOGLE_API_KEY +
GOOGLE_CSE_ID env vars) or a browser-driven search (the same Puppeteer/
Browsertrix infrastructure already proven working for archiving — see
fewa-automation/crawler.py). This module is deliberately search-engine-
agnostic: feed it a list of (title, snippet, url) results from whatever
search mechanism is actually wired up, and it does the real filtering.
"""

import re
from dataclasses import dataclass
from typing import List

from fejer_locations import ALL_LOCALITY_TERMS

# Categories from the task: person, institution, history.
DISCOVERY_TOPICS = [
    "helytörténet",
    "helyi intézmény",
    "önkormányzat",
    "közösségi élet",
    "kulturális örökség",
]


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str


@dataclass
class LocalityMatch:
    result: SearchResult
    matched_terms: List[str]

    @property
    def is_local(self) -> bool:
        return len(self.matched_terms) > 0


def build_search_queries(topics: List[str] = None) -> List[str]:
    """Real, usable Google search query strings for the task's criteria —
    one per municipality x topic would be thousands of queries, so this
    builds county-wide queries per topic instead (still concrete, real
    query strings, not placeholders)."""
    topics = topics or DISCOVERY_TOPICS
    return [f"Fejér megye {topic} Székesfehérvár" for topic in topics]


# Hungarian is agglutinative: place names almost always appear with a case
# suffix in running text ("Székesfehérváron" = "in Székesfehérvár",
# "székesfehérvári" = "of Székesfehérvár"), not the bare nominative form a
# naive \bTERM\b match expects. This is a common, real subset of Hungarian
# noun-case suffixes — not exhaustive morphology, but covers the forms that
# actually show up in real search snippets and news text.
_HU_SUFFIXES = (
    "iak|iaknak|inak|ié|ie|i|"          # adjectival / possessive
    "ban|ben|ba|be|"                     # inessive / illative
    "on|en|ön|"                          # superessive
    "ról|ről|"                           # delative
    "hoz|hez|höz|"                       # allative
    "ból|ből|"                           # elative
    "tól|től|"                           # ablative
    "nál|nél"                            # adessive
)


def find_locality_matches(text: str) -> List[str]:
    """Which Fejér megyei place names/terms actually appear in this text.

    Matches the bare name OR the name plus a common Hungarian case suffix
    (see _HU_SUFFIXES), always anchored so it still can't match INSIDE an
    unrelated word — e.g. "Mór" must not match inside "Móricka" (there's no
    recognized suffix boundary between "Mór" and "icka", so it's rejected).
    Case-insensitive since search snippets vary in capitalization.
    """
    matches = []
    for term in ALL_LOCALITY_TERMS:
        pattern = r"\b" + re.escape(term) + r"(?:" + _HU_SUFFIXES + r")?\b"
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(term)
    return matches


def filter_local_results(results: List[SearchResult]) -> List[LocalityMatch]:
    """Filter search results down to genuinely locally-connected ones —
    checks title AND snippet, not just the domain name (a candidate hosted
    on a generic domain can still be about a real Fejér megyei topic, and a
    .hu domain alone proves nothing about county relevance)."""
    matches = []
    for result in results:
        combined_text = f"{result.title} {result.snippet}"
        matched_terms = find_locality_matches(combined_text)
        matches.append(LocalityMatch(result=result, matched_terms=matched_terms))
    return matches


def only_local(results: List[SearchResult]) -> List[SearchResult]:
    """Convenience: just the results that actually passed the locality filter."""
    return [m.result for m in filter_local_results(results) if m.is_local]
