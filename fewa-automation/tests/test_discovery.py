"""Proves the locality filter genuinely discriminates Fejér megyei content
from unrelated content — using the real, sourced municipality list, not a
hand-picked toy list.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from discovery import (
    SearchResult,
    build_search_queries,
    filter_local_results,
    find_locality_matches,
    only_local,
)


def test_finds_exact_municipality_name():
    matches = find_locality_matches("Székesfehérvár város története")
    assert "Székesfehérvár" in matches


def test_word_boundary_prevents_false_positive_substring_match():
    """'Mór' must not match inside an unrelated word like 'móricka'."""
    matches = find_locality_matches("Ez egy móricka nevű szereplőről szól")
    assert "Mór" not in matches


def test_no_match_for_unrelated_text():
    matches = find_locality_matches("Ez a szöveg semmilyen megyéről nem szól, csak időjárásról")
    assert matches == []


def test_matches_county_level_term():
    matches = find_locality_matches("Fejér vármegyei hírek és programok")
    assert "Fejér vármegyei" in matches


def test_filter_local_results_separates_local_from_unrelated():
    results = [
        SearchResult(
            title="Székesfehérvári Csemete Alapítvány",
            snippet="Helyi civil szervezet Székesfehérváron",
            url="https://example.hu/csemete",
        ),
        SearchResult(
            title="Budapest belvárosi éttermek",
            snippet="A legjobb éttermek a fővárosban",
            url="https://example.hu/budapest-etterem",
        ),
        SearchResult(
            title="Mór városi híradó",
            snippet="Mór önkormányzatának hivatalos közleménye",
            url="https://mor.hu/hirek",
        ),
    ]

    local = only_local(results)
    local_urls = {r.url for r in local}

    assert "https://example.hu/csemete" in local_urls
    assert "https://mor.hu/hirek" in local_urls
    assert "https://example.hu/budapest-etterem" not in local_urls
    assert len(local) == 2


def test_build_search_queries_produces_real_nonempty_strings():
    queries = build_search_queries()
    assert len(queries) > 0
    for q in queries:
        assert "Fejér megye" in q
        assert len(q) > 10
