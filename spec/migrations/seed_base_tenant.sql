-- Base tenant seed — required before any sites/users/etc. can be inserted
-- (all reference tenant_id NOT NULL). Idempotent (ON CONFLICT DO NOTHING).
INSERT INTO tenants (id, slug, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'vmk', 'Vörösmarty Mihály Könyvtár')
ON CONFLICT (id) DO NOTHING;
