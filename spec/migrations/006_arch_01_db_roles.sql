-- =============================================================================
-- Migration 006: ARCH-01 database role boundary and always-on guards
-- transaction_mode=transactional
--
-- Preconditions: infra/postgres/bootstrap_roles.sql has been run by the
-- bootstrap-only superuser and transferred public object ownership to
-- fewa_migrator.  This migration is executed only by infra/migrations/runner.py
-- as fewa_migrator; it deliberately contains no password or bootstrap secret.
-- =============================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fewa_migrator')
       OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fewa_app') THEN
        RAISE EXCEPTION 'ARCH-01 role provisioning is required before migration 006';
    END IF;
END;
$$;

-- 005 is executed exclusively by the separate bootstrap executor.  It must
-- have normalised ownership and removed any historic bridge before the normal
-- migrator is even allowed to apply this migration.
DO $$
BEGIN
    IF pg_has_role('fewa_migrator', 'pg_read_server_files', 'member')
       OR pg_has_role('fewa_app', 'pg_read_server_files', 'member') THEN
        RAISE EXCEPTION 'ARCH-01 bootstrap cleanup did not remove server-file capability';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.arch01_bootstrap_operations
        WHERE stage = 'cleanup' AND result = 'success'
          AND (role_membership_after->>'migrator_file_read') = 'false'
          AND (role_membership_after->>'app_file_read') = 'false'
    ) THEN
        RAISE EXCEPTION 'ARCH-01 bootstrap cleanup audit is required before migration 006';
    END IF;
    IF (SELECT pg_get_userbyid(c.relowner) FROM pg_class c
        WHERE c.oid = 'public.arch01_bootstrap_operations'::regclass) <> 'fewa_bootstrap'
       OR (SELECT pg_get_userbyid(p.proowner) FROM pg_proc p
           WHERE p.oid = 'public.arch01_validate_bootstrap_audit_write()'::regprocedure) <> 'fewa_bootstrap' THEN
        RAISE EXCEPTION 'ARCH-01 bootstrap audit authority must remain bootstrap-owned';
    END IF;
    IF has_table_privilege('fewa_migrator', 'public.arch01_bootstrap_operations', 'INSERT')
       OR has_table_privilege('fewa_migrator', 'public.arch01_bootstrap_operations', 'UPDATE')
       OR has_table_privilege('fewa_migrator', 'public.arch01_bootstrap_operations', 'DELETE')
       OR has_table_privilege('fewa_app', 'public.arch01_bootstrap_operations', 'SELECT,INSERT,UPDATE,DELETE') THEN
        RAISE EXCEPTION 'ARCH-01 runtime role has forbidden bootstrap audit write/read privilege';
    END IF;
END;
$$;

-- No ambient/public permission may make a future table, function or sequence
-- executable by the runtime principal.  The allow-list below is intentional.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
-- Bootstrap-owned audit authority is intentionally outside migrator object
-- ownership.  Its grants were revoked during provision; do not issue generic
-- REVOKE ON ALL FUNCTIONS here because PostgreSQL correctly rejects a
-- non-owner trying to administer that bootstrap function.

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM fewa_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM fewa_app;
REVOKE CREATE ON SCHEMA public FROM fewa_app;

DO $$
BEGIN
    IF has_function_privilege('fewa_migrator', 'public.arch01_validate_bootstrap_audit_write()', 'EXECUTE')
       OR has_function_privilege('fewa_app', 'public.arch01_validate_bootstrap_audit_write()', 'EXECUTE') THEN
        RAISE EXCEPTION 'ARCH-01 bootstrap audit enforcement function must not be executable by runtime roles';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public TO fewa_app;

-- Runtime DML allow-list.  schema_migrations is deliberately absent: runtime
-- containers cannot inspect, alter, or erase migration authority.
GRANT SELECT, INSERT, UPDATE ON TABLE
    public.tenants,
    public.users,
    public.collections,
    public.municipalities,
    public.sites,
    public.crawl_policies,
    public.archived_snapshots,
    public.lifecycle_events,
    public.page_chunks,
    public.ai_traces,
    public.skos_concepts,
    public.jobs,
    public.audit_logs,
    public.discovery_candidates,
    public.discovery_evidence,
    public.artifacts,
    public.crawl_policy_revisions,
    public.crawl_policy_holds,
    public.legacy_snapshot_migrations,
    public.release_decisions,
    public.transactional_outbox
TO fewa_app;

GRANT SELECT ON TABLE
    public.v_published_snapshots,
    public.v_admin_queue,
    public.v_site_collection_status
TO fewa_app;
GRANT USAGE, SELECT ON SEQUENCE public.pid_sequence TO fewa_app;

ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public
    REVOKE ALL ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public
    REVOKE ALL ON TABLES FROM fewa_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM fewa_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public
    REVOKE ALL ON FUNCTIONS FROM fewa_app;

-- Every business guard stays live even under a hypothetical replication-role
-- session.  The app role cannot set that role or alter a table, but this keeps
-- DB authority intact as a separate, durable guard.
ALTER TABLE public.schema_migrations ENABLE ALWAYS TRIGGER trg_arch01_migration_ledger_immutable;
ALTER TABLE public.archived_snapshots ENABLE ALWAYS TRIGGER trg_arch01_snapshot_insert_guard;
ALTER TABLE public.archived_snapshots ENABLE ALWAYS TRIGGER trg_lifecycle_guard;
ALTER TABLE public.archived_snapshots ENABLE ALWAYS TRIGGER trg_arch01_release_state_guard;
ALTER TABLE public.archived_snapshots ENABLE ALWAYS TRIGGER trg_arch01_published_snapshot_artifact_immutable;
ALTER TABLE public.release_decisions ENABLE ALWAYS TRIGGER trg_arch01_release_decision_guard;
ALTER TABLE public.release_decisions ENABLE ALWAYS TRIGGER trg_arch01_release_decision_immutable;
ALTER TABLE public.artifacts ENABLE ALWAYS TRIGGER trg_arch01_released_artifact_immutable;
ALTER TABLE public.artifacts ENABLE ALWAYS TRIGGER trg_arch01_verified_artifact_binding_immutable;
ALTER TABLE public.crawl_policies ENABLE ALWAYS TRIGGER trg_arch01_policy_activation_guard;
ALTER TABLE public.crawl_policy_revisions ENABLE ALWAYS TRIGGER trg_arch01_policy_revision_immutable;
ALTER TABLE public.crawl_policy_holds ENABLE ALWAYS TRIGGER trg_arch01_policy_hold_guard;
ALTER TABLE public.jobs ENABLE ALWAYS TRIGGER trg_arch01_policy_execution;
ALTER TABLE public.discovery_candidates ENABLE ALWAYS TRIGGER trg_arch01_manual_candidate;
ALTER TABLE public.discovery_candidates ENABLE ALWAYS TRIGGER trg_arch01_candidate_transition_guard;
ALTER TABLE public.legacy_snapshot_migrations ENABLE ALWAYS TRIGGER trg_arch01_legacy_mapping_immutable;

COMMIT;
