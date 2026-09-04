# Webarchivum — Product Owner outcome clarification — 2026-09-04

**Authority:** Product Owner
**Status:** APPROVED PRODUCT INPUT / implementation details require joint agent review where unresolved

## 1. Core product outcome

A successful archive is not merely a completed crawl or a WACZ file. The archived website must be **actually usable when replayed**.

The Product Owner reports that many currently saved pages are defective in replay: links do not work and images/resources fail to load. This is a product failure even when the crawl technically completed or an internal QA score appears acceptable.

## 2. Key innovation expected from Webarchivum

One of the project's defining innovations is **automatic AI-assisted quality assurance of every archive**.

The system must not rely only on crawl completion, HTTP-level checks, or a synthetic score. It must automatically inspect the saved/replayed result and determine whether the archive is materially faithful and usable.

At minimum, the design/review must explicitly address:

- images and other visible resources actually loading in replay;
- internal links/navigation working in the replayed archive where they should;
- missing/broken resources and broken URLs being detected;
- material text/content omissions being detected;
- replay quality being evaluated from the visitor-visible result, not merely from crawl-time capture telemetry;
- the system recording concrete evidence for detected quality failures;
- automatic retry/remediation where technically safe and useful;
- a low-quality archive not being silently treated as successful/publishable.

## 3. Product acceptance principle

`crawl completed`, `WACZ exists`, `HTTP 200`, or an internal QA percentage alone are **not sufficient acceptance criteria**.

A representative archived page must be checked through a real browser/replay path. The QA result must correlate with what a real visitor actually sees.

If the system says an archive is good while the replay visibly contains broken images/links/materially missing content, the QA system itself has failed.

## 4. Required joint review before broad implementation

Claude, Codex, Gemini and ChatGPT must jointly reconcile:

1. what the current QA actually measures today;
2. why known bad replays can receive apparently acceptable QA results;
3. which layer is failing in each class of defect: capture, WACZ packaging/indexing, replay, URL rewriting, JS/dynamic content, resource policy, or QA measurement;
4. what deterministic checks and what AI/vision/reasoning checks are appropriate;
5. what automatic retry/remediation loop is technically safe;
6. what evidence is shown to the curator/PO;
7. the smallest real-browser acceptance corpus using actual archived sites, including known defective saves.

Do not begin another architecture rewrite without first producing this reconciled failure model and acceptance contract.

## 5. Open Product Owner questions

Only questions that genuinely affect product behavior should be returned to the Product Owner. Technical choices should be resolved by the agents.

Likely unresolved PO-level dimensions include:

- whether every internal link must be captured/replayable or whether bounded/declared exclusions are acceptable for very large/dynamic sites;
- what minimum replay quality is acceptable before publication;
- whether automatic remediation may trigger a full recrawl or only bounded retries without curator approval.

These questions must be surfaced concretely, with examples/trade-offs, not as abstract architecture questions.
