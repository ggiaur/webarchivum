-- =============================================================================
-- Migration 007: restore the legacy candidate/QC/publish lifecycle edges
-- transaction_mode=transactional
--
-- Regression found 2026-08-14: migration 005's arch01_validate_lifecycle_
-- transition() CASE statement only defined transitions for the NEW ARCH-01
-- states (crawling onward: archived_pending_qc / qc_passed_pending_release /
-- ...). It never had branches for 'candidate', 'archived' or 'indexed' --
-- the legacy status vocabulary app/crud/archive.py has used all along and
-- that S3 has not migrated off of yet. Every one of the following, still
-- actively used by the live admin UI, was silently broken:
--   candidate  -> approved   (approve_candidate, admin "jóváhagyás")
--   candidate  -> withdrawn  (reject_candidate, admin "elutasítás")
--   crawling   -> candidate  (revert_stalled_crawl, the arq_worker reconciler)
--   crawling   -> archived   (record_crawl_result, after a real crawl finishes)
--   archived   -> indexed    (record_qc_result auto-accept; decide_quality_review accept)
--   archived   -> candidate  (decide_quality_review reject)
--   indexed    -> published  (_publish, called by both of the above)
-- This was never an intentional part of the ARCH-01 design -- nothing in
-- ADR-0002 or any COLLAB_GEMINI.old.md acceptance/QA round called for
-- blocking any of these; every round exercised the NEW release/publish
-- boundary (qc_passed_pending_release -> published) and the withdrawal
-- gate, never this earlier legacy chain.
--
-- Publish-gate carve-out, per BJ's explicit 2026-08-14 decision: the
-- legacy indexed -> published edge does not create a release_decisions
-- row (that machinery belongs to the separate, not-yet-integrated ARCH-01
-- gated path) and is exempted from that requirement below. This is safe
-- because publish is only ever reached from 'indexed', and 'indexed' is
-- only ever reached two ways: (a) record_qc_result's auto-accept branch,
-- gated on qc_score >= QUALITY_AUTO_ACCEPT_THRESHOLD (currently 96, i.e.
-- stricter than BJ's stated 95% floor), or (b) decide_quality_review's
-- explicit curator accept-decision, which records a real actor
-- (approved_by) and reason. Neither is the unauthenticated bare-average
-- auto-publish this project has otherwise closed off; both require either
-- a high objective match score or a real recorded human decision.
--
-- Everything else in this function -- the entire qc_passed_pending_release
-- -> published gate (artifact/version binding, first-domain two-person
-- check), and the withdrawal gate for every state other than 'candidate'
-- -- is unchanged from 005/007's prior text.
-- =============================================================================

BEGIN;

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
        WHEN 'candidate' THEN allowed := ARRAY['approved', 'withdrawn'];
        WHEN 'approved' THEN allowed := ARRAY['crawling', 'withdrawn'];
        WHEN 'crawling' THEN allowed := ARRAY['archived', 'candidate', 'archived_pending_qc', 'qc_review_required', 'integrity_failed', 'withdrawn'];
        WHEN 'archived' THEN allowed := ARRAY['indexed', 'candidate'];
        WHEN 'indexed' THEN allowed := ARRAY['published'];
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
        IF OLD.lifecycle_status = 'indexed' THEN
            -- Legacy publish path -- see header comment for why this is
            -- exempted from the release_decisions requirement below.
            NEW.release_state := 'released';
            INSERT INTO transactional_outbox (aggregate_type, aggregate_id, event_type, payload, deduplication_key)
            VALUES ('archived_snapshot', NEW.id, 'snapshot.released',
                    jsonb_build_object('snapshot_id', NEW.id, 'release_state', 'released', 'origin', 'legacy_indexed'),
                    'snapshot.released:' || NEW.id::text)
            ON CONFLICT (deduplication_key) DO NOTHING;
        ELSE
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
        -- Only the legacy reject_candidate() edge (candidate -> withdrawn,
        -- app/crud/archive.py) is exempted from the full release-decision
        -- requirement below -- that is the one and only lifecycle_status =
        -- 'withdrawn' call site in the current legacy CRUD layer. Every
        -- other source state (approved, crawling, and all post-QC/publish
        -- states) still requires the authenticated, idempotent withdrawal
        -- decision, unchanged from 005.
        IF decision_actor IS NULL AND OLD.lifecycle_status <> 'candidate' THEN
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

COMMIT;
