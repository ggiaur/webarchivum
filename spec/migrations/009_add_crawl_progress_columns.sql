-- Migration 009: Add real-time crawl progress columns to archived_snapshots
ALTER TABLE archived_snapshots
    ADD COLUMN IF NOT EXISTS pages_crawled INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS current_depth INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_pages INTEGER DEFAULT 25;
