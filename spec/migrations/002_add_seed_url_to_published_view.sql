-- v_published_snapshots (spec/schema.sql) was missing seed_url, which the
-- public search API needs to display/link to the original source domain.
-- CREATE OR REPLACE VIEW is safe/idempotent as long as only columns are
-- appended, not reordered or removed.
CREATE OR REPLACE VIEW v_published_snapshots AS
SELECT
    s.id,
    s.pid,
    s.dc_title,
    s.dc_description,
    s.ai_summary,
    s.dc_subject,
    s.municipality_id,
    m.name AS municipality_name,
    m.slug AS municipality_slug,
    s.crawl_timestamp,
    s.qc_score,
    s.search_vector,
    si.domain,
    si.display_name AS site_name,
    si.category AS site_category,
    si.priority AS site_priority,
    si.oszk_status,
    s.seed_url
FROM archived_snapshots s
JOIN sites si ON si.id = s.site_id
LEFT JOIN municipalities m ON m.id = s.municipality_id
WHERE s.lifecycle_status = 'published';
