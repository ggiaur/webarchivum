-- Real seed data: Fejér vármegye municipalities. Previously this same list
-- lived hardcoded in app/api/v1/municipalities.py with fabricated
-- non-UUID ids ("muni-001-szekesfehervar") and was never backed by the
-- real municipalities table at all — GET /api/municipalities served it
-- directly instead of querying the DB. Idempotent on slug.
INSERT INTO municipalities (name, slug, county, is_active, sort_order) VALUES
    ('Székesfehérvár', 'szekesfehervar', 'Fejér', TRUE, 10),
    ('Dunaújváros',    'dunauvaros',     'Fejér', TRUE, 20),
    ('Mór',            'mor',            'Fejér', TRUE, 30),
    ('Bicske',         'bicske',         'Fejér', TRUE, 40),
    ('Sárbogárd',      'sarbogard',      'Fejér', TRUE, 50),
    ('Gárdony',        'gardony',        'Fejér', TRUE, 60),
    ('Enying',         'enying',         'Fejér', TRUE, 70),
    ('Martonvásár',    'martonvasar',    'Fejér', TRUE, 80),
    ('Velence',        'velence',        'Fejér', TRUE, 90),
    ('Szabadbattyán',  'szabadbattyan',  'Fejér', FALSE, 999)
ON CONFLICT (slug) DO NOTHING;
