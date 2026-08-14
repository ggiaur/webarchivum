-- Local demonstration data only.  It deliberately creates one transparent
-- manual candidate so the curator queue can be demonstrated without claiming
-- that an AI locality assessment or a WACZ crawl has taken place.
WITH seeded_site AS (
    INSERT INTO sites (
        tenant_id, domain, base_url, display_name, priority, category,
        crawl_frequency, is_active_collection
    ) VALUES (
        '00000000-0000-0000-0000-000000000001',
        'fewa.vmk.hu',
        'https://fewa.vmk.hu/',
        'DEMO – FEWA: kézi felvitel, AI ellenőrzés még nem futott',
        'medium',
        'kulturális',
        'once',
        FALSE
    )
    ON CONFLICT (tenant_id, domain) DO UPDATE
        SET base_url = EXCLUDED.base_url,
            display_name = EXCLUDED.display_name
    RETURNING id
), seeded_candidate AS (
    INSERT INTO archived_snapshots (
        tenant_id, site_id, seed_url, dc_title, dc_description,
        lifecycle_status, lifecycle_reason, created_by
    )
    SELECT
        '00000000-0000-0000-0000-000000000001',
        seeded_site.id,
        'https://fewa.vmk.hu/',
        'DEMO – FEWA: kézi felvitel, AI ellenőrzés még nem futott',
        'DEMO jelölt: kézzel felvett referencia-URL. Nincs AI helyi tartalom-ellenőrzés, crawl vagy WACZ-archívum.',
        'candidate',
        'DEMO_SEED: manual reference candidate; no AI assessment or crawl has run.',
        '550e8400-e29b-41d4-a716-446655440000'
    FROM seeded_site
    WHERE NOT EXISTS (
        SELECT 1
        FROM archived_snapshots existing
        WHERE existing.tenant_id = '00000000-0000-0000-0000-000000000001'
          AND existing.seed_url = 'https://fewa.vmk.hu/'
          AND existing.lifecycle_status = 'candidate'
    )
    RETURNING id
)
INSERT INTO lifecycle_events (
    snapshot_id, from_status, to_status, triggered_by, reason, metadata
)
SELECT
    id,
    NULL,
    'candidate',
    '550e8400-e29b-41d4-a716-446655440000',
    'DEMO_SEED: manual reference candidate; no AI assessment or crawl has run.',
    '{"source":"demo_seed","ai_assessment":"not_run","crawl":"not_run"}'::jsonb
FROM seeded_candidate;
