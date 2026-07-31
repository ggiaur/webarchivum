-- =============================================================================
-- Migration 001: qc_detail column for real Browsertrix QA breakdown
-- =============================================================================
-- The existing archived_snapshots.qc_score (SMALLINT 0-100) can only hold a
-- single number, but the real, official Browsertrix QA mode (see
-- fewa-automation/crawler.py::run_qa(), live-verified 2026-07-31) produces
-- THREE separate metrics per page: screenshotMatch, textMatch, and
-- resourceCounts. This column preserves the full breakdown; qc_score stays
-- as a single derived summary value (e.g. min or average of the two match
-- scores * 100) for the existing indexes/views to keep working unchanged.
--
-- Run: psql -U fewa_admin -d fewa_v3 -f spec/migrations/001_add_qc_detail.sql
-- =============================================================================

BEGIN;

ALTER TABLE archived_snapshots
    ADD COLUMN IF NOT EXISTS qc_detail JSONB;

COMMENT ON COLUMN archived_snapshots.qc_detail IS
    'Full Browsertrix QA breakdown: {"screenshotMatch": 0.99, "textMatch": 0.98, '
    '"resourceCounts": {"crawlGood": N, "crawlBad": N, "replayGood": N, "replayBad": N}}. '
    'qc_score is a derived single-number summary of this; this column has the real detail '
    'shown in the admin quality-review UI.';

COMMIT;
