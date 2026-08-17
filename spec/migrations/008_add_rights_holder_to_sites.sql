-- Migration 008: Add rights holder & contact information fields to sites table
ALTER TABLE sites
    ADD COLUMN IF NOT EXISTS rights_holder_name TEXT,
    ADD COLUMN IF NOT EXISTS rights_holder_email TEXT,
    ADD COLUMN IF NOT EXISTS rights_holder_contact_other TEXT,
    ADD COLUMN IF NOT EXISTS permission_status TEXT DEFAULT 'nincs_megkeresve';
