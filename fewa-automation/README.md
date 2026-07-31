# fewa-automation

Standalone content-discovery, archiving, and quality-verification pipeline
for the FEWA (Fejér Vármegyei Webarchívum) project. Built alongside — not
inside — both the legacy WordPress+PHP+pywb system and the half-finished
`fewa-v3-backend` rewrite. Never touches either.

## Modules

- `fejer_locations.py` — 108 real Fejér county municipalities (source:
  fejer.hu, fetched 2026-07-31), used as ground truth for locality matching.
- `discovery.py` — builds Google-search queries for the task criteria (local
  people/institutions/history) and filters candidate results by genuine
  locality match (handles Hungarian case suffixes, e.g. "Székesfehérváron").
- `crawler.py` — real Browsertrix crawl invocation (`run_crawl`) and the
  **official Browsertrix QA mode** (`run_qa`) — see "Real proof" below.
- `quality_index.py` — a simpler, dependency-free text-similarity fallback
  (archived vs. live) for cases where the full Browsertrix QA re-crawl isn't
  needed/wanted. Prefer `run_qa()` for real quality assessment; this exists
  as a lighter-weight alternative.

## Real, verified end-to-end proof (2026-07-31)

```
$ python3 -c "from crawler import run_crawl; ..."
crawl success: True
wacz: .../vmk_autoclick_test/vmk_autoclick_test.wacz

$ python3 -c "from crawler import run_qa; ..."
QA success: True
{'url': 'https://www.vmk.hu/',
 'screenshotMatch': 0.9929,   # 99.29% visual pixel match, crawl vs replay
 'textMatch': 0.9875,         # 98.75% Levenshtein text match
 'resourceCounts': {'crawlGood': 92, 'crawlBad': 0, 'replayGood': 88, 'replayBad': 10}}
```

These are real numbers from Browsertrix-Crawler 1.14.1's own QA re-crawl —
not estimated. The `run_qa()` docstring documents exactly where this data
actually lives (the run's log file, not `pages.jsonl` as the hosted docs
imply) since that took real debugging to find.

## Known operational notes

- **`--shm-size=1g` is mandatory** on `docker run` for the crawler — without
  it, headless Chrome silently hangs (discovered via a real stuck crawl).
- **Crawl scope is always domain-restricted** (`--scopeType host` default) —
  verified live that it correctly excludes both external domains AND
  sibling subdomains (e.g. crawling `www.vmk.hu` correctly skips
  `helyismeret.vmk.hu`, `konyvtar.vmk.hu`, facebook.com, etc.). Trade-off:
  this can be too strict if a site's relevant content genuinely lives on a
  subdomain — consider `scopeType="domain"` per-seed if needed.
- **Cookie-consent banners**: `run_crawl()` enables Browsertrix's
  `autoclick` behavior with a best-effort selector
  (`DEFAULT_COOKIE_CONSENT_SELECTOR`) targeting common consent-plugin accept
  buttons. Verified live (visual screenshot inspection via a real,
  non-headless Chrome) that an unhandled consent banner can otherwise block
  a page from rendering further content.
- **ReplayWeb.page (public-facing replay) calibration is UNRESOLVED** — see
  git history / previous_answer.md in the ai-sd-os project for the honest
  account of what was and wasn't measured. Don't treat any specific
  file-size threshold here as confirmed; the design instead relies on a
  runtime timeout-triggered fallback to pywb, which is safe regardless of
  the exact number.
- Requires Docker with internet access to pull `webrecorder/browsertrix-crawler`
  and `webrecorder/pywb` images (one-time).

## Local test/demo artifacts (gitignored territory, not checked in state)

`crawl-output-sample/`, `scope-test-output/`, `qa-test-output*/`,
`pywb-data/`, `replay-test-server/` are all local, disposable outputs from
manual verification runs (some contain root-owned files from Docker — use
`docker run --rm -v $(pwd):/data alpine rm -rf /data/<dir>` to clean up, not
plain `rm -rf`, if you hit permission errors).
