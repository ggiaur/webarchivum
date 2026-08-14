-- ARCH-01 bootstrap-only role provisioner.
--
-- Execute as the image-created superuser, once per cluster, before the runner:
--   psql "$BOOTSTRAP_DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -v migrator_password="$MIGRATOR_PASSWORD" -v app_password="$APP_PASSWORD" \
--     -f /bootstrap/bootstrap_roles.sql
--
-- Passwords are psql variables, never literals in this repository.  Existing
-- clusters must be drained and backed up before this ownership hand-off.
\if :{?migrator_password}
\else
\quit 3
\endif
\if :{?app_password}
\else
\quit 3
\endif

DO $$
BEGIN
    IF session_user <> 'fewa_bootstrap' THEN
        RAISE EXCEPTION 'ARCH-01 provision must be run by the dedicated fewa_bootstrap principal';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fewa_bootstrap') THEN
        RAISE EXCEPTION 'dedicated fewa_bootstrap principal must exist before provision';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fewa_migrator') THEN
        CREATE ROLE fewa_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fewa_app') THEN
        CREATE ROLE fewa_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS NOINHERIT;
    END IF;
END;
$$;

-- psql quotes the supplied values safely before the dynamic role statement.
ALTER ROLE fewa_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD :'migrator_password';
ALTER ROLE fewa_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD :'app_password';
REVOKE fewa_bootstrap FROM fewa_migrator;
REVOKE fewa_bootstrap FROM fewa_app;
REVOKE fewa_migrator FROM fewa_app;
REVOKE pg_read_server_files FROM fewa_migrator;
REVOKE pg_read_server_files FROM fewa_app;
REVOKE EXECUTE ON FUNCTION pg_catalog.pg_read_binary_file(text) FROM fewa_migrator;
REVOKE EXECUTE ON FUNCTION pg_catalog.pg_read_binary_file(text) FROM fewa_app;

-- Bootstrap-stage evidence is immutable and deliberately unavailable to the
-- runtime role.  The short-lived bootstrap executor writes one complete row
-- per stage; a failed/missing cleanup row blocks migration 006.
CREATE TABLE IF NOT EXISTS public.arch01_bootstrap_operations (
    operation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bootstrap_session_user TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN ('provision', '005', 'ownership_normalise', 'cleanup')),
    source_sha256 CHAR(64),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    role_membership_before JSONB NOT NULL,
    role_membership_after JSONB NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('success', 'failure')),
    error_text TEXT,
    CHECK ((result = 'success' AND error_text IS NULL) OR (result = 'failure' AND error_text IS NOT NULL))
);
-- This table is an authority boundary, not an ordinary application relation.
-- It remains bootstrap-owned even though the surrounding public schema is
-- deliberately owned by fewa_migrator for ordinary versioned DDL.
ALTER TABLE public.arch01_bootstrap_operations OWNER TO fewa_bootstrap;
CREATE OR REPLACE FUNCTION public.arch01_validate_bootstrap_audit_write()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND session_user = 'fewa_bootstrap'
       AND current_user = 'fewa_bootstrap'
       AND NEW.bootstrap_session_user = session_user THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'ARCH-01 bootstrap audit accepts inserts only from dedicated bootstrap session and is otherwise append-only';
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION public.arch01_validate_bootstrap_audit_write() OWNER TO fewa_bootstrap;
DROP TRIGGER IF EXISTS trg_arch01_bootstrap_audit_immutable ON public.arch01_bootstrap_operations;
CREATE TRIGGER trg_arch01_bootstrap_audit_immutable
BEFORE INSERT OR UPDATE OR DELETE ON public.arch01_bootstrap_operations
FOR EACH ROW EXECUTE FUNCTION public.arch01_validate_bootstrap_audit_write();
ALTER TABLE public.arch01_bootstrap_operations
    ENABLE ALWAYS TRIGGER trg_arch01_bootstrap_audit_immutable;
REVOKE ALL ON TABLE public.arch01_bootstrap_operations FROM PUBLIC, fewa_app, fewa_migrator;
REVOKE ALL ON FUNCTION public.arch01_validate_bootstrap_audit_write() FROM PUBLIC, fewa_app, fewa_migrator;

-- Transfer every existing public object without changing data or object IDs.
-- New ARCH-01 objects will subsequently be created by fewa_migrator itself.
DO $$
DECLARE obj record;
BEGIN
    EXECUTE 'ALTER SCHEMA public OWNER TO fewa_migrator';
    FOR obj IN
        SELECT c.oid::regclass AS identity,
               CASE c.relkind
                   WHEN 'S' THEN 'SEQUENCE'
                   WHEN 'v' THEN 'VIEW'
                   WHEN 'm' THEN 'MATERIALIZED VIEW'
                   WHEN 'f' THEN 'FOREIGN TABLE'
                   ELSE 'TABLE'
               END AS object_kind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S','f')
          AND c.relname <> 'arch01_bootstrap_operations'
    LOOP
        EXECUTE format('ALTER %s %s OWNER TO fewa_migrator', obj.object_kind, obj.identity);
    END LOOP;
    FOR obj IN
        SELECT t.oid::regtype AS identity
        FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typtype IN ('b','c','d','e','r')
          AND t.typelem = 0
          AND t.typrelid = 0
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_type'::regclass
                AND d.objid = t.oid AND d.deptype = 'e'
          )
    LOOP
        EXECUTE format('ALTER TYPE %s OWNER TO fewa_migrator', obj.identity);
    END LOOP;
    FOR obj IN
        SELECT p.oid::regprocedure AS identity
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname <> 'arch01_validate_bootstrap_audit_write'
    LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO fewa_migrator', obj.identity);
    END LOOP;
END;
$$;

DO $$
BEGIN
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO fewa_migrator, fewa_app', current_database());
END;
$$;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public
    REVOKE ALL ON FUNCTIONS FROM PUBLIC;

-- 006 needs to validate the bootstrap cleanup evidence but may never forge,
-- mutate or administer it.  No application role receives even this read.
GRANT SELECT ON TABLE public.arch01_bootstrap_operations TO fewa_migrator;

-- Provision audit after all role/ownership normalisation.  The bootstrap
-- executor will append 005, ownership_normalise and cleanup evidence.
INSERT INTO public.arch01_bootstrap_operations (
    bootstrap_session_user, stage, started_at, completed_at,
    role_membership_before, role_membership_after, result
) VALUES (
    session_user, 'provision', now(), now(),
    jsonb_build_object('migrator_file_read', false, 'app_file_read', false),
    jsonb_build_object('migrator_file_read', false, 'app_file_read', false),
    'success'
);

-- Compatibility rollback boundary: do not revoke legacy login here.  An
-- operator does that only after the migration runner and app connection pass.
