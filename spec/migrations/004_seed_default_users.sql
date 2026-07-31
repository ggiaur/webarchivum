-- Real seed data for the two accounts app/api/v1/auth.py previously served
-- from a hardcoded in-memory MOCK_USERS_DB. Same emails/passwords/roles/ids
-- as before (so existing credentials keep working) — only the storage is
-- now real. Password hashes are real bcrypt (cost=12), generated once via
-- app.core.security.hash_password(); bcrypt hashes are self-contained
-- (salt included), so re-running this is safe/idempotent regardless.
INSERT INTO users (id, tenant_id, email, password_hash, role, full_name, is_active) VALUES
    (
        '550e8400-e29b-41d4-a716-446655440000',
        '00000000-0000-0000-0000-000000000001',
        'curator@vmk.hu',
        '$2b$12$kEhUxG/EA8FsbnyBm0aE4eNbkCYd7g14hp24jeQ6HsNcSvHNq8tWa',
        'curator',
        'VMK Kurátor',
        TRUE
    ),
    (
        '00000000-0000-0000-0000-000000000099',
        '00000000-0000-0000-0000-000000000001',
        'admin@vmk.hu',
        '$2b$12$y7K6HMnp6Dq.uHt2B.lz4OrYYFyCWzxsk5X94b33CP7y33BZTfxuC',
        'admin',
        'System Admin',
        TRUE
    )
ON CONFLICT (id) DO NOTHING;
