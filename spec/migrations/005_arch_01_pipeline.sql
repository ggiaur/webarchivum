-- =============================================================================
-- Migration 005: ARCH-01 database-authoritative release pipeline
-- transaction_mode=enum_phased
--
-- Runner contract (normative): run Phase A on a fresh, runner-owned autocommit
-- connection under the session advisory lock.  The runner must then run Phase B
-- as one transaction and insert its checksum ledger row in that same commit.
-- It must reject an outer caller transaction, checksum drift and partial Phase B.
-- =============================================================================

-- PHASE A (autocommit only; do not add DML or DDL other than enum labels here)
ALTER TYPE lifecycle_status_enum ADD VALUE IF NOT EXISTS 'migration_hold';
ALTER TYPE lifecycle_status_enum ADD VALUE IF NOT EXISTS 'archived_pending_qc';
ALTER TYPE lifecycle_status_enum ADD VALUE IF NOT EXISTS 'qc_passed_pending_release';
ALTER TYPE lifecycle_status_enum ADD VALUE IF NOT EXISTS 'qc_review_required';
ALTER TYPE lifecycle_status_enum ADD VALUE IF NOT EXISTS 'integrity_failed';

-- PHASE B (the migration runner owns this one transaction)
BEGIN;

-- The runner verifies the source checksum before Phase A and then records this
-- immutable migration identity in the same Phase-B commit as every schema and
-- data change.  A conflicting prior ledger row is a fail-closed condition.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    checksum CHAR(64) NOT NULL,
    transaction_mode TEXT NOT NULL CHECK (transaction_mode IN ('transactional', 'enum_phased')),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
DECLARE
    source_path TEXT := current_setting('arch01.migration_source_path', true);
    expected_checksum CHAR(64);
    recorded_checksum CHAR(64);
BEGIN
    -- The runner passes its read-only source path.  The /workspace fallback is
    -- solely for the isolated, read-only migration fixture; absence of both is
    -- fail-closed rather than recording a made-up checksum.
    source_path := COALESCE(source_path, '/workspace/spec/migrations/005_arch_01_pipeline.sql');
    expected_checksum := encode(digest(pg_read_binary_file(source_path), 'sha256'), 'hex');
    SELECT checksum INTO recorded_checksum FROM schema_migrations WHERE version = '005';
    IF recorded_checksum IS NOT NULL AND recorded_checksum <> expected_checksum THEN
        RAISE EXCEPTION 'ARCH-01 migration 005 checksum mismatch';
    END IF;
    INSERT INTO schema_migrations (version, checksum, transaction_mode)
    VALUES ('005', expected_checksum, 'enum_phased')
    ON CONFLICT (version) DO NOTHING;
END $$;

CREATE OR REPLACE FUNCTION arch01_reject_migration_ledger_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'ARCH-01 migration ledger is immutable';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_migration_ledger_immutable ON schema_migrations;
CREATE TRIGGER trg_arch01_migration_ledger_immutable
    BEFORE UPDATE OR DELETE ON schema_migrations
    FOR EACH ROW EXECUTE FUNCTION arch01_reject_migration_ledger_mutation();

DO $$
BEGIN
    CREATE TYPE candidate_state_enum AS ENUM (
        'discovered', 'prequalified', 'uncertain', 'rejected', 'suppressed',
        'curator_approved', 'curator_rejected'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE candidate_origin_enum AS ENUM ('discovery', 'manual', 'legacy_migration');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE decision_source_enum AS ENUM (
        'deterministic', 'llm', 'provider_failure', 'budget_exhausted',
        'model_failure', 'security_rejected', 'manual', 'legacy_migration'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE reason_code_enum AS ENUM (
        'locality_match', 'non_local', 'content_uncertain', 'duplicate',
        'prior_suppression', 'provider_failed', 'budget_exhausted',
        'model_timeout', 'model_invalid_output', 'evidence_invalid',
        'prompt_injection_signal', 'security_rejected', 'policy_rejected',
        'manual_review', 'legacy_candidate_requires_reapproval',
        'legacy_approval_requires_reapproval', 'legacy_inflight_requires_reapproval',
        'legacy_artifact_retained', 'legacy_deprecated_retained'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE release_state_enum AS ENUM (
        'not_ready', 'review_required', 'release_pending', 'released', 'held', 'withdrawn'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE arch01_policy_execution_state_enum AS ENUM ('active', 'on_hold', 'retired');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS discovery_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    landing_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    host TEXT,
    etld_plus_one TEXT,
    content_sha256 CHAR(64),
    state candidate_state_enum NOT NULL DEFAULT 'discovered',
    candidate_origin candidate_origin_enum NOT NULL DEFAULT 'discovery',
    decision_source decision_source_enum NOT NULL,
    reason_code reason_code_enum NOT NULL,
    confidence NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1),
    submitted_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    submitted_at TIMESTAMPTZ,
    submitter_rationale TEXT,
    immutable_submission_evidence JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT discovery_candidates_canonical_unique UNIQUE (tenant_id, canonical_url),
    CONSTRAINT arch01_manual_candidate_shape CHECK (
        candidate_origin <> 'manual' OR
        (state IN ('uncertain', 'curator_approved') AND decision_source = 'manual' AND reason_code = 'manual_review'
         AND submitted_by IS NOT NULL AND submitted_at IS NOT NULL
         AND length(btrim(submitter_rationale)) > 0 AND immutable_submission_evidence IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS discovery_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES discovery_candidates(id) ON DELETE RESTRICT,
    evidence_kind TEXT NOT NULL CHECK (evidence_kind IN ('provider', 'inspection', 'llm_input', 'llm_output', 'submission')),
    artifact_sha256 CHAR(64) NOT NULL,
    artifact_uri TEXT,
    input_sha256 CHAR(64),
    prompt_sha256 CHAR(64),
    prompt_template_version TEXT,
    validator_version TEXT,
    model_id TEXT,
    model_digest TEXT,
    byte_start INTEGER CHECK (byte_start >= 0),
    byte_end INTEGER CHECK (byte_end >= byte_start),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID UNIQUE REFERENCES archived_snapshots(id) ON DELETE RESTRICT,
    object_key TEXT NOT NULL,
    object_version_id TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    filesize_bytes BIGINT NOT NULL CHECK (filesize_bytes >= 0),
    readback_sha256 CHAR(64),
    validator_report_sha256 CHAR(64),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT artifact_verified_consistent CHECK (
        verified_at IS NULL OR (readback_sha256 = sha256 AND validator_report_sha256 IS NOT NULL)
    ),
    CONSTRAINT artifact_object_version_unique UNIQUE (object_key, object_version_id)
);

CREATE TABLE IF NOT EXISTS crawl_policy_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID NOT NULL REFERENCES crawl_policies(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL CHECK (revision > 0),
    config_json JSONB NOT NULL,
    config_hash CHAR(64) NOT NULL,
    depth_hops SMALLINT NOT NULL CHECK (depth_hops BETWEEN 0 AND 2),
    source TEXT NOT NULL CHECK (source IN ('legacy_normalized', 'curator_reapproval', 'arch01')),
    supersedes_revision_id UUID REFERENCES crawl_policy_revisions(id) ON DELETE RESTRICT,
    created_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    reviewed_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ,
    review_reason TEXT NOT NULL CHECK (length(btrim(review_reason)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT crawl_policy_revisions_unique UNIQUE (policy_id, revision),
    CONSTRAINT arch01_revision_reviewed CHECK (
        source = 'legacy_normalized' OR (created_by IS NOT NULL AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    )
);

ALTER TABLE crawl_policies
    ADD COLUMN IF NOT EXISTS arch01_execution_state arch01_policy_execution_state_enum NOT NULL DEFAULT 'on_hold',
    ADD COLUMN IF NOT EXISTS active_revision_id UUID REFERENCES crawl_policy_revisions(id) ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS crawl_policy_holds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID NOT NULL REFERENCES crawl_policies(id) ON DELETE RESTRICT,
    legacy_depth SMALLINT NOT NULL CHECK (legacy_depth BETWEEN 3 AND 5),
    legacy_config_hash CHAR(64) NOT NULL,
    legacy_is_active BOOLEAN NOT NULL,
    hold_reason TEXT NOT NULL CHECK (hold_reason = 'legacy_depth_exceeds_arch01'),
    opened_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cleared_by_revision_id UUID REFERENCES crawl_policy_revisions(id) ON DELETE RESTRICT,
    cleared_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    cleared_at TIMESTAMPTZ,
    clear_reason TEXT,
    CONSTRAINT crawl_policy_holds_one_per_policy UNIQUE (policy_id),
    CONSTRAINT arch01_hold_clear_complete CHECK (
        (cleared_by_revision_id IS NULL AND cleared_by IS NULL AND cleared_at IS NULL AND clear_reason IS NULL)
        OR (cleared_by_revision_id IS NOT NULL AND cleared_by IS NOT NULL AND cleared_at IS NOT NULL
            AND length(btrim(clear_reason)) > 0)
    )
);

CREATE TABLE IF NOT EXISTS legacy_snapshot_migrations (
    snapshot_id UUID PRIMARY KEY REFERENCES archived_snapshots(id) ON DELETE RESTRICT,
    legacy_lifecycle_status lifecycle_status_enum NOT NULL,
    migration_version TEXT NOT NULL DEFAULT '005',
    migrated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    disposition TEXT NOT NULL CHECK (disposition IN (
        'requires_reapproval', 'artifact_retained', 'legacy_grandfathered',
        'legacy_deprecated_retained', 'withdrawn_retained'
    )),
    resumable_candidate_id UUID REFERENCES discovery_candidates(id) ON DELETE RESTRICT,
    import_hash CHAR(64) NOT NULL,
    CONSTRAINT arch01_legacy_mapping_candidate CHECK (
        (disposition = 'requires_reapproval' AND resumable_candidate_id IS NOT NULL)
        OR (disposition <> 'requires_reapproval' AND resumable_candidate_id IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS release_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES archived_snapshots(id) ON DELETE RESTRICT,
    operation TEXT NOT NULL CHECK (operation IN ('release', 'override', 'withdraw', 'legacy_import')),
    decision_origin TEXT NOT NULL CHECK (decision_origin IN ('arch01_gate', 'g4_override', 'legacy_grandfathered')),
    outcome TEXT NOT NULL CHECK (outcome IN ('released', 'held', 'withdrawn')),
    gate_matrix_hash CHAR(64),
    artifact_id UUID REFERENCES artifacts(id) ON DELETE RESTRICT,
    artifact_sha256 CHAR(64),
    policy_revision_id UUID REFERENCES crawl_policy_revisions(id) ON DELETE RESTRICT,
    actor_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    curator_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    admin_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    actor_reason TEXT,
    curator_reason TEXT,
    admin_reason TEXT,
    idempotency_key TEXT,
    request_hash CHAR(64),
    response_hash CHAR(64),
    original_published_at TIMESTAMPTZ,
    import_hash CHAR(64),
    transaction_id BIGINT NOT NULL DEFAULT txid_current(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT arch01_release_idempotency UNIQUE NULLS NOT DISTINCT (snapshot_id, operation, actor_id, idempotency_key),
    CONSTRAINT arch01_release_principals CHECK (
        decision_origin = 'legacy_grandfathered' OR
        (actor_id IS NOT NULL AND length(btrim(actor_reason)) > 0 AND idempotency_key IS NOT NULL
         AND request_hash IS NOT NULL AND response_hash IS NOT NULL)
    ),
    CONSTRAINT arch01_two_person_gate CHECK (
        decision_origin NOT IN ('g4_override') OR
        (curator_id IS NOT NULL AND admin_id IS NOT NULL AND curator_id <> admin_id
         AND length(btrim(curator_reason)) > 0 AND length(btrim(admin_reason)) > 0)
    )
);

CREATE TABLE IF NOT EXISTS transactional_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type TEXT NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    deduplication_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    dispatched_at TIMESTAMPTZ,
    dispatch_attempts INTEGER NOT NULL DEFAULT 0 CHECK (dispatch_attempts >= 0)
);

ALTER TABLE archived_snapshots
    ADD COLUMN IF NOT EXISTS release_state release_state_enum NOT NULL DEFAULT 'not_ready',
    ADD COLUMN IF NOT EXISTS artifact_id UUID REFERENCES artifacts(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS discovery_candidate_id UUID REFERENCES discovery_candidates(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS policy_revision_id UUID REFERENCES crawl_policy_revisions(id) ON DELETE RESTRICT;

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS policy_revision_id UUID REFERENCES crawl_policy_revisions(id) ON DELETE RESTRICT;

-- Retain legacy policy input exactly.  Depth 3--5 becomes non-executable;
-- depth 1--2 receives an immutable normalised revision without rewriting depth.
INSERT INTO crawl_policy_holds (policy_id, legacy_depth, legacy_config_hash, legacy_is_active, hold_reason)
SELECT cp.id, cp.depth,
       encode(digest(to_jsonb(cp)::text, 'sha256'), 'hex'), cp.is_active,
       'legacy_depth_exceeds_arch01'
FROM crawl_policies cp
WHERE cp.depth IN (3, 4, 5)
ON CONFLICT (policy_id) DO NOTHING;

UPDATE crawl_policies cp
SET arch01_execution_state = 'on_hold', active_revision_id = NULL
WHERE cp.depth IN (3, 4, 5);

INSERT INTO crawl_policy_revisions (policy_id, revision, config_json, config_hash, depth_hops, source, review_reason)
SELECT cp.id, 1, to_jsonb(cp), encode(digest(to_jsonb(cp)::text, 'sha256'), 'hex'),
       cp.depth, 'legacy_normalized', 'legacy normalized under ARCH-01 migration'
FROM crawl_policies cp
WHERE cp.depth IN (1, 2)
ON CONFLICT (policy_id, revision) DO NOTHING;

UPDATE crawl_policies cp
SET arch01_execution_state = CASE WHEN cp.is_active THEN 'active'::arch01_policy_execution_state_enum ELSE 'retired'::arch01_policy_execution_state_enum END,
    active_revision_id = r.id
FROM crawl_policy_revisions r
WHERE r.policy_id = cp.id AND r.revision = 1 AND cp.depth IN (1, 2);

-- Make existing queued/running legacy crawls non-executable before enforcing a
-- revision reference.  They remain audited instead of being silently resumed.
UPDATE jobs
SET status = 'dead_lettered', error_message = 'ARCH-01 migration: legacy crawl requires approved policy revision'
WHERE job_type = 'crawl' AND status IN ('queued', 'running') AND policy_revision_id IS NULL;

-- The new trigger is installed before lifecycle mapping; the migration-only GUC
-- permits exactly the lossless mapping below and no normal post-005 transition.
DROP TRIGGER IF EXISTS trg_lifecycle_guard ON archived_snapshots;

CREATE OR REPLACE FUNCTION arch01_user_has_active_role(user_id_value UUID, allowed_roles user_role_enum[])
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM users
        WHERE id = user_id_value AND is_active AND role = ANY(allowed_roles)
    );
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION arch01_validate_snapshot_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- Snapshots are never born public.  The old direct INSERT bypass is denied
    -- even if a caller supplies a superficially matching release_state.
    IF NEW.lifecycle_status IN ('published', 'migration_hold') OR NEW.release_state IN ('released', 'held') THEN
        RAISE EXCEPTION 'ARCH-01 snapshot insert may not set publication or migration-retention state';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_snapshot_insert_guard ON archived_snapshots;
CREATE TRIGGER trg_arch01_snapshot_insert_guard
    BEFORE INSERT ON archived_snapshots
    FOR EACH ROW EXECUTE FUNCTION arch01_validate_snapshot_insert();

CREATE OR REPLACE FUNCTION arch01_validate_release_decision()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.decision_origin = 'legacy_grandfathered' THEN
        -- A historical import record is retained even if it was imported by an
        -- audit tool, but it is *never* a valid runtime release credential:
        -- the lifecycle trigger accepts only arch01_gate/g4_override origins.
        RETURN NEW;
    END IF;

    IF NEW.operation = 'legacy_import' OR NEW.actor_id IS NULL OR
       NOT arch01_user_has_active_role(NEW.actor_id, ARRAY['curator', 'admin']::user_role_enum[]) OR
       NEW.gate_matrix_hash IS NULL OR NEW.artifact_sha256 IS NULL OR
       NEW.idempotency_key IS NULL OR NEW.request_hash IS NULL OR NEW.response_hash IS NULL OR
       length(btrim(COALESCE(NEW.actor_reason, ''))) = 0 THEN
        RAISE EXCEPTION 'ARCH-01 release decision requires an active curator/admin actor and complete hash-bound idempotency evidence';
    END IF;

    IF NEW.decision_origin = 'g4_override' AND
       (NOT arch01_user_has_active_role(NEW.curator_id, ARRAY['curator']::user_role_enum[])
        OR NOT arch01_user_has_active_role(NEW.admin_id, ARRAY['admin']::user_role_enum[])) THEN
        RAISE EXCEPTION 'ARCH-01 G4 override requires active curator and admin principals';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_release_decision_guard ON release_decisions;
CREATE TRIGGER trg_arch01_release_decision_guard
    BEFORE INSERT ON release_decisions
    FOR EACH ROW EXECUTE FUNCTION arch01_validate_release_decision();

CREATE OR REPLACE FUNCTION arch01_reject_release_decision_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'ARCH-01 release decisions are immutable';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_release_decision_immutable ON release_decisions;
CREATE TRIGGER trg_arch01_release_decision_immutable
    BEFORE UPDATE OR DELETE ON release_decisions
    FOR EACH ROW EXECUTE FUNCTION arch01_reject_release_decision_mutation();

CREATE OR REPLACE FUNCTION arch01_reject_released_artifact_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM archived_snapshots s
        JOIN release_decisions rd ON rd.snapshot_id = s.id
        WHERE s.artifact_id = OLD.id
          AND rd.artifact_id = OLD.id
          AND rd.outcome = 'released'
          AND rd.decision_origin IN ('arch01_gate', 'g4_override')
    ) THEN
        RAISE EXCEPTION 'ARCH-01 released artifact identity/version/integrity fields are immutable, including after withdrawal';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_released_artifact_immutable ON artifacts;
CREATE TRIGGER trg_arch01_released_artifact_immutable
    BEFORE UPDATE OF snapshot_id, object_key, object_version_id, sha256,
                     filesize_bytes, readback_sha256, validator_report_sha256, verified_at
    ON artifacts
    FOR EACH ROW EXECUTE FUNCTION arch01_reject_released_artifact_mutation();

CREATE OR REPLACE FUNCTION arch01_reject_verified_artifact_rebind()
RETURNS TRIGGER AS $$
BEGIN
    -- Before verification an executor may finish preparing the row.  Once an
    -- artifact is verified, its snapshot and integrity identity cannot be
    -- moved or rewritten, even before a later release decision exists.
    IF OLD.verified_at IS NOT NULL AND (
        NEW.verified_at IS DISTINCT FROM OLD.verified_at
        OR NEW.snapshot_id IS DISTINCT FROM OLD.snapshot_id
        OR NEW.sha256 IS DISTINCT FROM OLD.sha256
        OR NEW.readback_sha256 IS DISTINCT FROM OLD.readback_sha256
        OR NEW.validator_report_sha256 IS DISTINCT FROM OLD.validator_report_sha256
        OR NEW.object_key IS DISTINCT FROM OLD.object_key
        OR NEW.object_version_id IS DISTINCT FROM OLD.object_version_id
    ) THEN
        RAISE EXCEPTION 'ARCH-01 verified artifact state and snapshot/integrity binding are immutable';
    END IF;
    IF OLD.verified_at IS NULL AND NEW.verified_at IS NOT NULL AND
       (NEW.sha256 IS NULL
        OR NEW.readback_sha256 IS NULL
        OR NEW.readback_sha256 IS DISTINCT FROM NEW.sha256
        OR NEW.validator_report_sha256 IS NULL) THEN
        RAISE EXCEPTION 'ARCH-01 verification requires non-null matching readback SHA-256 and validator report';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_verified_artifact_binding_immutable ON artifacts;
CREATE TRIGGER trg_arch01_verified_artifact_binding_immutable
    BEFORE UPDATE OF snapshot_id, object_key, object_version_id, sha256,
                     readback_sha256, validator_report_sha256, verified_at
    ON artifacts
    FOR EACH ROW EXECUTE FUNCTION arch01_reject_verified_artifact_rebind();

CREATE OR REPLACE FUNCTION arch01_reject_published_snapshot_artifact_relink()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.artifact_id IS DISTINCT FROM OLD.artifact_id
       AND EXISTS (
            SELECT 1 FROM release_decisions rd
            WHERE rd.snapshot_id = OLD.id
              AND rd.artifact_id = OLD.artifact_id
              AND rd.outcome = 'released'
              AND rd.decision_origin IN ('arch01_gate', 'g4_override')
       ) THEN
        RAISE EXCEPTION 'ARCH-01 released snapshot artifact binding is immutable, including after withdrawal';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_published_snapshot_artifact_immutable ON archived_snapshots;
CREATE TRIGGER trg_arch01_published_snapshot_artifact_immutable
    BEFORE UPDATE OF artifact_id ON archived_snapshots
    FOR EACH ROW EXECUTE FUNCTION arch01_reject_published_snapshot_artifact_relink();

CREATE OR REPLACE FUNCTION arch01_validate_lifecycle_transition()
RETURNS TRIGGER AS $$
DECLARE
    allowed TEXT[];
    decision_actor UUID;
    release_curator UUID;
    release_admin UUID;
    first_domain_snapshot BOOLEAN;
BEGIN
    IF OLD.lifecycle_status = NEW.lifecycle_status THEN
        RETURN NEW;
    END IF;

    IF NEW.lifecycle_status = 'migration_hold' AND current_setting('arch01.migration_mode', true) = '005' THEN
        INSERT INTO lifecycle_events (snapshot_id, from_status, to_status, reason, metadata)
        VALUES (NEW.id, OLD.lifecycle_status, NEW.lifecycle_status, NEW.lifecycle_reason,
                jsonb_build_object('migration', '005'));
        RETURN NEW;
    END IF;

    CASE OLD.lifecycle_status::text
        WHEN 'approved' THEN allowed := ARRAY['crawling', 'withdrawn'];
        WHEN 'crawling' THEN allowed := ARRAY['archived_pending_qc', 'qc_review_required', 'integrity_failed', 'withdrawn'];
        WHEN 'archived_pending_qc' THEN allowed := ARRAY['qc_passed_pending_release', 'qc_review_required', 'integrity_failed', 'withdrawn'];
        WHEN 'qc_passed_pending_release' THEN allowed := ARRAY['published', 'qc_review_required', 'withdrawn'];
        WHEN 'qc_review_required' THEN allowed := ARRAY['qc_passed_pending_release', 'integrity_failed', 'withdrawn'];
        WHEN 'integrity_failed' THEN allowed := ARRAY['withdrawn'];
        WHEN 'published' THEN allowed := ARRAY['withdrawn'];
        ELSE allowed := ARRAY[]::TEXT[];
    END CASE;

    IF NOT (NEW.lifecycle_status::text = ANY(allowed)) THEN
        RAISE EXCEPTION 'ARCH-01 invalid lifecycle transition: % -> %', OLD.lifecycle_status, NEW.lifecycle_status;
    END IF;

    IF NEW.lifecycle_status = 'published' THEN
        SELECT rd.actor_id, rd.curator_id, rd.admin_id
        INTO decision_actor, release_curator, release_admin
        FROM release_decisions rd
        WHERE rd.snapshot_id = NEW.id
          AND rd.decision_origin IN ('arch01_gate', 'g4_override')
          AND rd.outcome = 'released'
          AND rd.gate_matrix_hash IS NOT NULL
          AND rd.artifact_id = NEW.artifact_id
          AND EXISTS (
              SELECT 1 FROM artifacts a
              WHERE a.id = rd.artifact_id
                AND a.snapshot_id = NEW.id
                AND a.sha256 = rd.artifact_sha256
                AND a.readback_sha256 = a.sha256
                AND a.validator_report_sha256 IS NOT NULL
                AND a.verified_at IS NOT NULL
          )
          AND rd.transaction_id = txid_current()
        ORDER BY rd.created_at DESC
        LIMIT 1;
        IF decision_actor IS NULL THEN
            RAISE EXCEPTION 'ARCH-01 publish requires same-transaction release bound to current verified artifact/version';
        END IF;

        SELECT NOT EXISTS (
            SELECT 1
            FROM archived_snapshots prior
            JOIN sites prior_site ON prior_site.id = prior.site_id
            JOIN sites current_site ON current_site.id = NEW.site_id
            WHERE prior.lifecycle_status = 'published'
              AND prior.id <> NEW.id
              AND lower(regexp_replace(prior_site.domain, '^www\\.', '')) =
                  lower(regexp_replace(current_site.domain, '^www\\.', ''))
        ) INTO first_domain_snapshot;
        IF first_domain_snapshot AND
           (NOT COALESCE(arch01_user_has_active_role(release_curator, ARRAY['curator']::user_role_enum[]), FALSE)
            OR NOT COALESCE(arch01_user_has_active_role(release_admin, ARRAY['admin']::user_role_enum[]), FALSE)
            OR release_curator IS NULL OR release_admin IS NULL OR release_curator = release_admin) THEN
            RAISE EXCEPTION 'ARCH-01 first domain snapshot requires distinct active curator and admin approvals';
        END IF;
        NEW.release_state := 'released';
        INSERT INTO transactional_outbox (aggregate_type, aggregate_id, event_type, payload, deduplication_key)
        VALUES ('archived_snapshot', NEW.id, 'snapshot.released',
                jsonb_build_object('snapshot_id', NEW.id, 'release_state', 'released'),
                'snapshot.released:' || NEW.id::text)
        ON CONFLICT (deduplication_key) DO NOTHING;
    END IF;

    IF NEW.lifecycle_status = 'withdrawn' THEN
        SELECT rd.actor_id INTO decision_actor
        FROM release_decisions rd
        WHERE rd.snapshot_id = NEW.id
          AND rd.operation = 'withdraw'
          AND rd.decision_origin IN ('arch01_gate', 'g4_override')
          AND rd.outcome = 'withdrawn'
          AND rd.transaction_id = txid_current()
          AND rd.actor_id IS NOT NULL
          AND length(btrim(COALESCE(rd.actor_reason, ''))) > 0
          AND rd.idempotency_key IS NOT NULL
          AND rd.request_hash IS NOT NULL
          AND rd.response_hash IS NOT NULL
        ORDER BY rd.created_at DESC
        LIMIT 1;
        IF decision_actor IS NULL THEN
            RAISE EXCEPTION 'ARCH-01 withdrawal requires same-transaction authenticated idempotent withdrawal decision';
        END IF;
        NEW.release_state := 'withdrawn';
        INSERT INTO transactional_outbox (aggregate_type, aggregate_id, event_type, payload, deduplication_key)
        VALUES ('archived_snapshot', NEW.id, 'snapshot.withdrawn',
                jsonb_build_object('snapshot_id', NEW.id, 'release_state', 'withdrawn'),
                'snapshot.withdrawn:' || NEW.id::text)
        ON CONFLICT (deduplication_key) DO NOTHING;
    END IF;

    INSERT INTO lifecycle_events (snapshot_id, from_status, to_status, triggered_by, reason, metadata)
    VALUES (NEW.id, OLD.lifecycle_status, NEW.lifecycle_status,
            COALESCE(decision_actor, NULLIF(current_setting('arch01.actor_id', true), '')::UUID),
            NEW.lifecycle_reason, '{}'::jsonb);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_lifecycle_guard
    BEFORE UPDATE OF lifecycle_status ON archived_snapshots
    FOR EACH ROW EXECUTE FUNCTION arch01_validate_lifecycle_transition();

CREATE OR REPLACE FUNCTION arch01_validate_release_state()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.release_state = OLD.release_state THEN
        RETURN NEW;
    END IF;
    IF current_setting('arch01.migration_mode', true) = '005' THEN
        RETURN NEW;
    END IF;
    IF NEW.release_state = 'released' AND NEW.lifecycle_status = 'published' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'ARCH-01 release_state is controlled by the release transition';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_release_state_guard ON archived_snapshots;
CREATE TRIGGER trg_arch01_release_state_guard
    BEFORE UPDATE OF release_state ON archived_snapshots
    FOR EACH ROW EXECUTE FUNCTION arch01_validate_release_state();

CREATE OR REPLACE FUNCTION arch01_validate_policy_execution()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.job_type = 'crawl' THEN
        IF NEW.policy_revision_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM crawl_policies cp
            JOIN crawl_policy_revisions r ON r.id = NEW.policy_revision_id AND r.policy_id = cp.id
            WHERE cp.arch01_execution_state = 'active' AND cp.active_revision_id = r.id
        ) THEN
            RAISE EXCEPTION 'ARCH-01 crawl job requires active approved policy revision';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION arch01_validate_policy_activation()
RETURNS TRIGGER AS $$
DECLARE
    revision_source TEXT;
    hold_cleared BOOLEAN;
BEGIN
    IF NEW.arch01_execution_state <> 'active' THEN
        RETURN NEW;
    END IF;
    IF NEW.active_revision_id IS NULL THEN
        RAISE EXCEPTION 'ARCH-01 active policy requires an approved revision';
    END IF;
    SELECT source INTO revision_source
    FROM crawl_policy_revisions
    WHERE id = NEW.active_revision_id AND policy_id = NEW.id;
    IF revision_source IS NULL THEN
        RAISE EXCEPTION 'ARCH-01 active revision does not belong to policy';
    END IF;
    SELECT EXISTS (
        SELECT 1 FROM crawl_policy_holds h
        WHERE h.policy_id = NEW.id
          AND h.cleared_by_revision_id = NEW.active_revision_id
          AND h.cleared_by IS NOT NULL AND h.cleared_at IS NOT NULL
          AND length(btrim(COALESCE(h.clear_reason, ''))) > 0
    ) INTO hold_cleared;
    IF EXISTS (SELECT 1 FROM crawl_policy_holds WHERE policy_id = NEW.id) AND
       (revision_source <> 'curator_reapproval' OR NOT hold_cleared) THEN
        RAISE EXCEPTION 'ARCH-01 held policy requires authenticated curator reapproval and cleared hold';
    END IF;
    IF revision_source = 'legacy_normalized' AND NEW.depth NOT IN (1, 2) THEN
        RAISE EXCEPTION 'ARCH-01 legacy normalized revision cannot activate a depth 3--5 policy';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_policy_activation_guard ON crawl_policies;
CREATE TRIGGER trg_arch01_policy_activation_guard
    BEFORE UPDATE OF arch01_execution_state, active_revision_id ON crawl_policies
    FOR EACH ROW EXECUTE FUNCTION arch01_validate_policy_activation();

CREATE OR REPLACE FUNCTION arch01_reject_policy_revision_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'ARCH-01 crawl policy revisions are append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_policy_revision_immutable ON crawl_policy_revisions;
CREATE TRIGGER trg_arch01_policy_revision_immutable
    BEFORE UPDATE OR DELETE ON crawl_policy_revisions
    FOR EACH ROW EXECUTE FUNCTION arch01_reject_policy_revision_mutation();

CREATE OR REPLACE FUNCTION arch01_reject_policy_hold_mutation()
RETURNS TRIGGER AS $$
BEGIN
    -- The only legal hold mutation is an authenticated curator reapproval
    -- written in the same transaction as the matching active revision.
    IF TG_OP = 'UPDATE' AND OLD.cleared_by_revision_id IS NULL
       AND NEW.policy_id = OLD.policy_id AND NEW.legacy_depth = OLD.legacy_depth
       AND NEW.legacy_config_hash = OLD.legacy_config_hash AND NEW.legacy_is_active = OLD.legacy_is_active
       AND NEW.hold_reason = OLD.hold_reason AND NEW.opened_by IS NOT DISTINCT FROM OLD.opened_by
       AND NEW.opened_at = OLD.opened_at
       AND NEW.cleared_by_revision_id IS NOT NULL AND NEW.cleared_by IS NOT NULL
       AND NEW.cleared_at IS NOT NULL AND length(btrim(COALESCE(NEW.clear_reason, ''))) > 0
       AND arch01_user_has_active_role(NEW.cleared_by, ARRAY['curator']::user_role_enum[])
       AND EXISTS (
            SELECT 1 FROM crawl_policy_revisions r
            WHERE r.id = NEW.cleared_by_revision_id AND r.policy_id = NEW.policy_id
              AND r.source = 'curator_reapproval'
              AND r.created_by = NEW.cleared_by
              AND r.reviewed_by IS NOT NULL
       ) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'ARCH-01 crawl policy holds are append-only except authenticated reapproval clearance';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_policy_hold_guard ON crawl_policy_holds;
CREATE TRIGGER trg_arch01_policy_hold_guard
    BEFORE UPDATE OR DELETE ON crawl_policy_holds
    FOR EACH ROW EXECUTE FUNCTION arch01_reject_policy_hold_mutation();

DROP TRIGGER IF EXISTS trg_arch01_policy_execution ON jobs;
CREATE TRIGGER trg_arch01_policy_execution
    BEFORE INSERT OR UPDATE OF job_type, policy_revision_id ON jobs
    FOR EACH ROW EXECUTE FUNCTION arch01_validate_policy_execution();

CREATE OR REPLACE FUNCTION arch01_validate_manual_candidate()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.candidate_origin = 'manual' AND
       (OLD.candidate_origin <> NEW.candidate_origin OR OLD.state <> NEW.state
        OR OLD.decision_source <> NEW.decision_source OR OLD.reason_code <> NEW.reason_code
        OR OLD.submitted_by <> NEW.submitted_by OR OLD.submitted_at <> NEW.submitted_at
        OR OLD.submitter_rationale <> NEW.submitter_rationale
        OR OLD.immutable_submission_evidence <> NEW.immutable_submission_evidence
        OR OLD.landing_url <> NEW.landing_url OR OLD.canonical_url <> NEW.canonical_url
        OR OLD.host IS DISTINCT FROM NEW.host OR OLD.etld_plus_one IS DISTINCT FROM NEW.etld_plus_one
        OR OLD.content_sha256 IS DISTINCT FROM NEW.content_sha256) AND NOT (
            OLD.state = 'uncertain' AND NEW.state = 'curator_approved'
            AND OLD.candidate_origin = NEW.candidate_origin
            AND OLD.decision_source = NEW.decision_source AND OLD.reason_code = NEW.reason_code
            AND OLD.submitted_by = NEW.submitted_by AND OLD.submitted_at = NEW.submitted_at
            AND OLD.submitter_rationale = NEW.submitter_rationale
            AND OLD.immutable_submission_evidence = NEW.immutable_submission_evidence
            AND OLD.landing_url = NEW.landing_url AND OLD.canonical_url = NEW.canonical_url
            AND OLD.host IS NOT DISTINCT FROM NEW.host AND OLD.etld_plus_one IS NOT DISTINCT FROM NEW.etld_plus_one
            AND OLD.content_sha256 IS NOT DISTINCT FROM NEW.content_sha256
        ) THEN
        RAISE EXCEPTION 'ARCH-01 manual candidate provenance is immutable';
    END IF;
    IF NEW.candidate_origin = 'manual' AND TG_OP = 'INSERT' AND
       (NEW.state <> 'uncertain' OR NEW.decision_source <> 'manual' OR NEW.reason_code <> 'manual_review') THEN
        RAISE EXCEPTION 'ARCH-01 manual candidate must start uncertain with manual_review';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_manual_candidate ON discovery_candidates;
CREATE TRIGGER trg_arch01_manual_candidate
    BEFORE INSERT OR UPDATE ON discovery_candidates
    FOR EACH ROW EXECUTE FUNCTION arch01_validate_manual_candidate();

CREATE UNIQUE INDEX IF NOT EXISTS ux_arch01_snapshot_candidate
    ON archived_snapshots (discovery_candidate_id)
    WHERE discovery_candidate_id IS NOT NULL;

CREATE OR REPLACE FUNCTION arch01_validate_candidate_transition()
RETURNS TRIGGER AS $$
DECLARE
    actor_id_value UUID;
    policy_revision_id_value UUID;
    snapshot_id_value UUID;
BEGIN
    IF OLD.state = NEW.state THEN
        RETURN NEW;
    END IF;
    IF OLD.state <> 'uncertain' OR NEW.state <> 'curator_approved' THEN
        RAISE EXCEPTION 'ARCH-01 candidate transition is not permitted: % -> %', OLD.state, NEW.state;
    END IF;

    actor_id_value := NULLIF(current_setting('arch01.actor_id', true), '')::UUID;
    policy_revision_id_value := NULLIF(current_setting('arch01.policy_revision_id', true), '')::UUID;
    IF actor_id_value IS NULL
       OR NOT arch01_user_has_active_role(actor_id_value, ARRAY['curator', 'admin']::user_role_enum[])
       OR policy_revision_id_value IS NULL
       OR NEW.site_id IS NULL
       OR NOT EXISTS (
            SELECT 1 FROM crawl_policies cp
            JOIN crawl_policy_revisions pr ON pr.id = policy_revision_id_value AND pr.policy_id = cp.id
            WHERE cp.site_id = NEW.site_id
              AND cp.arch01_execution_state = 'active'
              AND cp.active_revision_id = pr.id
       ) THEN
        RAISE EXCEPTION 'ARCH-01 curator approval requires active actor, candidate site and active approved policy revision';
    END IF;

    INSERT INTO archived_snapshots (
        tenant_id, site_id, lifecycle_status, lifecycle_reason, seed_url,
        created_by, approved_by, discovery_candidate_id, policy_revision_id
    ) VALUES (
        NEW.tenant_id, NEW.site_id, 'approved', 'ARCH-01 curator candidate approval', NEW.canonical_url,
        actor_id_value, actor_id_value, NEW.id, policy_revision_id_value
    ) RETURNING id INTO snapshot_id_value;

    INSERT INTO transactional_outbox (aggregate_type, aggregate_id, event_type, payload, deduplication_key)
    VALUES ('discovery_candidate', NEW.id, 'candidate.approved',
            jsonb_build_object('candidate_id', NEW.id, 'snapshot_id', snapshot_id_value,
                               'policy_revision_id', policy_revision_id_value),
            'candidate.approved:' || NEW.id::text)
    ON CONFLICT (deduplication_key) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_candidate_transition_guard ON discovery_candidates;
CREATE TRIGGER trg_arch01_candidate_transition_guard
    BEFORE UPDATE OF state ON discovery_candidates
    FOR EACH ROW EXECUTE FUNCTION arch01_validate_candidate_transition();

CREATE OR REPLACE FUNCTION arch01_reject_legacy_mapping_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'ARCH-01 legacy snapshot migration evidence is immutable';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_arch01_legacy_mapping_immutable ON legacy_snapshot_migrations;
CREATE TRIGGER trg_arch01_legacy_mapping_immutable
    BEFORE UPDATE OR DELETE ON legacy_snapshot_migrations
    FOR EACH ROW EXECUTE FUNCTION arch01_reject_legacy_mapping_mutation();

SELECT set_config('arch01.migration_mode', '005', true);

-- Candidate/approved/crawling legacy records each obtain a deduplicated,
-- uncertain reapproval candidate.  The retained snapshot never resumes.
INSERT INTO discovery_candidates (
    tenant_id, landing_url, canonical_url, state, candidate_origin,
    decision_source, reason_code, confidence
)
SELECT DISTINCT ON (s.tenant_id, s.seed_url)
    s.tenant_id, s.seed_url, s.seed_url, 'uncertain', 'legacy_migration',
    'legacy_migration',
    CASE s.lifecycle_status
        WHEN 'candidate' THEN 'legacy_candidate_requires_reapproval'::reason_code_enum
        WHEN 'approved' THEN 'legacy_approval_requires_reapproval'::reason_code_enum
        ELSE 'legacy_inflight_requires_reapproval'::reason_code_enum
    END,
    NULL
FROM archived_snapshots s
WHERE s.lifecycle_status IN ('candidate', 'approved', 'crawling')
ORDER BY s.tenant_id, s.seed_url, s.created_at
ON CONFLICT (tenant_id, canonical_url) DO NOTHING;

INSERT INTO legacy_snapshot_migrations (
    snapshot_id, legacy_lifecycle_status, disposition, resumable_candidate_id, import_hash
)
SELECT s.id, s.lifecycle_status, 'requires_reapproval', c.id,
       encode(digest(concat_ws('|', s.id::text, s.lifecycle_status::text, s.seed_url), 'sha256'), 'hex')
FROM archived_snapshots s
JOIN discovery_candidates c ON c.tenant_id = s.tenant_id AND c.canonical_url = s.seed_url
WHERE s.lifecycle_status IN ('candidate', 'approved', 'crawling')
ON CONFLICT (snapshot_id) DO NOTHING;

INSERT INTO legacy_snapshot_migrations (snapshot_id, legacy_lifecycle_status, disposition, import_hash)
SELECT s.id, s.lifecycle_status,
       CASE s.lifecycle_status
           WHEN 'archived' THEN 'artifact_retained'
           WHEN 'indexed' THEN 'artifact_retained'
           WHEN 'published' THEN 'legacy_grandfathered'
           WHEN 'deprecated' THEN 'legacy_deprecated_retained'
           WHEN 'withdrawn' THEN 'withdrawn_retained'
       END,
       encode(digest(concat_ws('|', s.id::text, s.lifecycle_status::text, s.seed_url), 'sha256'), 'hex')
FROM archived_snapshots s
WHERE s.lifecycle_status IN ('archived', 'indexed', 'published', 'deprecated', 'withdrawn')
ON CONFLICT (snapshot_id) DO NOTHING;

UPDATE archived_snapshots s
SET lifecycle_status = 'migration_hold', release_state = 'held',
    lifecycle_reason = 'ARCH-01 legacy retention: new capture requires a separately reviewed candidate'
WHERE s.lifecycle_status IN ('candidate', 'approved', 'crawling', 'archived', 'indexed', 'deprecated');

UPDATE archived_snapshots
SET release_state = 'released'
WHERE lifecycle_status = 'published';

UPDATE archived_snapshots
SET release_state = 'withdrawn'
WHERE lifecycle_status = 'withdrawn';

INSERT INTO release_decisions (
    snapshot_id, operation, decision_origin, outcome, original_published_at, import_hash
)
SELECT s.id, 'legacy_import', 'legacy_grandfathered', 'released',
       COALESCE(s.crawl_timestamp, s.created_at), l.import_hash
FROM archived_snapshots s
JOIN legacy_snapshot_migrations l ON l.snapshot_id = s.id
WHERE s.lifecycle_status = 'published'
ON CONFLICT DO NOTHING;

SELECT set_config('arch01.migration_mode', '', true);

COMMIT;
