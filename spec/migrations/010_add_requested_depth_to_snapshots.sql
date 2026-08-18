-- Migration 010: Persist the curator's requested crawl depth alongside the
-- already-existing max_pages column, so approve_candidate_endpoint can read
-- back what was actually requested at ingest time instead of hardcoding
-- depth=2 (see COLLAB_GEMINI.md, "depth/max_pages elveszik jóváhagyáskor").
ALTER TABLE archived_snapshots
    ADD COLUMN IF NOT EXISTS requested_depth SMALLINT DEFAULT 2;
