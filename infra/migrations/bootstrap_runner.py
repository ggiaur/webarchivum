"""Narrow bootstrap-only executor for immutable ARCH-01 migration 005.

This is intentionally not a generic runner.  It accepts only a bootstrap DSN,
the fixed server-visible source mount and exactly migration version 005.  Once
005 has committed it normalises ownership, revokes legacy file-read capability
from both runtime roles and appends immutable audit evidence before 006 can run.
"""
from __future__ import annotations

import hashlib
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from runner import LOCK_SQL, UNLOCK_SQL, MigrationError, _enum_phases, load_migrations


FIXED_DB_SOURCE = "/fixed/read-only/migrations/005_arch_01_pipeline.sql"


def membership(connection: psycopg.Connection) -> dict[str, bool]:
    row = connection.execute(
        """SELECT pg_has_role('fewa_migrator', 'pg_read_server_files', 'member'),
                  pg_has_role('fewa_app', 'pg_read_server_files', 'member')"""
    ).fetchone()
    return {"migrator_file_read": bool(row[0]), "app_file_read": bool(row[1])}


def append_audit(
    connection: psycopg.Connection,
    stage: str,
    started: datetime,
    before: dict[str, bool],
    after: dict[str, bool],
    result: str,
    source_sha256: str | None = None,
    error: str | None = None,
) -> None:
    connection.execute(
        """INSERT INTO public.arch01_bootstrap_operations
           (bootstrap_session_user, stage, source_sha256, started_at, completed_at,
            role_membership_before, role_membership_after, result, error_text)
           VALUES (session_user, %s, %s, %s, now(), %s::jsonb, %s::jsonb, %s, %s)""",
        (stage, source_sha256, started, psycopg.types.json.Jsonb(before), psycopg.types.json.Jsonb(after), result, error),
    )


def normalise_ownership(connection: psycopg.Connection) -> None:
    """Transfer every public object without changing its identity or data."""
    connection.execute("ALTER SCHEMA public OWNER TO fewa_migrator")
    relations = connection.execute(
        """SELECT c.oid::regclass,
                  CASE c.relkind WHEN 'S' THEN 'SEQUENCE' WHEN 'v' THEN 'VIEW'
                    WHEN 'm' THEN 'MATERIALIZED VIEW' WHEN 'f' THEN 'FOREIGN TABLE'
                    ELSE 'TABLE' END
           FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')
             AND c.relname <> 'arch01_bootstrap_operations'"""
    ).fetchall()
    for identity, kind in relations:
        connection.execute(f"ALTER {kind} {identity} OWNER TO fewa_migrator")
    types = connection.execute(
        """SELECT t.oid::regtype FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
           WHERE n.nspname='public' AND t.typtype IN ('b','c','d','e','r')
             AND t.typelem=0 AND t.typrelid=0
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_type'::regclass
                             AND d.objid=t.oid AND d.deptype='e')"""
    ).fetchall()
    for (identity,) in types:
        connection.execute(f"ALTER TYPE {identity} OWNER TO fewa_migrator")
    functions = connection.execute(
        """SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public'
             AND p.proname <> 'arch01_validate_bootstrap_audit_write'"""
    ).fetchall()
    for (identity,) in functions:
        connection.execute(f"ALTER FUNCTION {identity} OWNER TO fewa_migrator")


def run(database_url: str, migration_dir: Path, only: str) -> None:
    if only != "005":
        raise MigrationError("bootstrap executor accepts only --only 005")
    migrations = {item.version: item for item in load_migrations(migration_dir)}
    migration = migrations.get("005")
    if migration is None:
        raise MigrationError("immutable migration 005 is missing")
    if migration.path.read_bytes() != Path(migration.path).read_bytes():
        raise MigrationError("unreadable immutable migration source")
    checksum = hashlib.sha256(migration.path.read_bytes()).hexdigest()
    phase_a, phase_b = _enum_phases(migration)
    with psycopg.connect(database_url, autocommit=True) as connection:
        if not connection.execute(LOCK_SQL).fetchone()[0]:
            raise MigrationError("another migration runner holds the advisory lock")
        try:
            if connection.execute("SELECT current_user = 'fewa_bootstrap'").fetchone()[0] is not True:
                raise MigrationError("bootstrap executor requires fewa_bootstrap")
            if not connection.execute("SELECT to_regclass('public.arch01_bootstrap_operations') IS NOT NULL").fetchone()[0]:
                raise MigrationError("bootstrap provision audit table is missing")
            pre_versions = [row[0] for row in connection.execute(
                "SELECT version FROM public.schema_migrations WHERE version IN ('001','002','003','004') ORDER BY version"
            ).fetchall()]
            if pre_versions != ["001", "002", "003", "004"]:
                raise MigrationError("bootstrap 005 requires successful migrator pre-stage through 004")
            before = membership(connection)
            existing = connection.execute(
                "SELECT checksum FROM public.schema_migrations WHERE version='005'"
            ).fetchone()
            started = datetime.now(timezone.utc)
            if existing is None:
                connection.execute(phase_a)
                with connection.transaction():
                    connection.execute("SELECT set_config('arch01.migration_source_path', %s, true)", (FIXED_DB_SOURCE,))
                    connection.execute(phase_b)
                    recorded = connection.execute(
                        "SELECT checksum FROM public.schema_migrations WHERE version='005'"
                    ).fetchone()
                    if recorded is None or recorded[0] != checksum:
                        raise MigrationError("005 ledger checksum did not match immutable source")
            elif existing[0] != checksum:
                raise MigrationError("migration 005 checksum drift")
            append_audit(connection, "005", started, before, membership(connection), "success", checksum)

            normalise_started = datetime.now(timezone.utc)
            normalise_ownership(connection)
            append_audit(connection, "ownership_normalise", normalise_started, membership(connection), membership(connection), "success", checksum)

            cleanup_started = datetime.now(timezone.utc)
            cleanup_before = membership(connection)
            connection.execute("REVOKE pg_read_server_files FROM fewa_migrator")
            connection.execute("REVOKE pg_read_server_files FROM fewa_app")
            connection.execute("REVOKE EXECUTE ON FUNCTION pg_catalog.pg_read_binary_file(text) FROM fewa_migrator")
            connection.execute("REVOKE EXECUTE ON FUNCTION pg_catalog.pg_read_binary_file(text) FROM fewa_app")
            cleanup_after = membership(connection)
            if cleanup_after["migrator_file_read"] or cleanup_after["app_file_read"]:
                raise MigrationError("bootstrap cleanup left server-file capability behind")
            append_audit(connection, "cleanup", cleanup_started, cleanup_before, cleanup_after, "success", checksum)
        except Exception as exc:
            # Do not hide bootstrap failure: append a best-effort durable record
            # if provision completed and the connection remains usable.
            try:
                append_audit(connection, "cleanup", datetime.now(timezone.utc), membership(connection), membership(connection), "failure", checksum, str(exc))
            except Exception:
                pass
            raise
        finally:
            connection.execute(UNLOCK_SQL)


def main() -> int:
    parser = argparse.ArgumentParser(description="ARCH-01 bootstrap-only immutable 005 executor")
    parser.add_argument("--only", metavar="VERSION")
    args = parser.parse_args()
    database_url = os.environ.get("BOOTSTRAP_DATABASE_URL")
    if not database_url or "MIGRATOR_DATABASE_URL" in os.environ:
        print("BOOTSTRAP_DATABASE_URL only is required", file=sys.stderr)
        return 2
    try:
        run(
            database_url,
            Path(os.environ.get("MIGRATIONS_DIR", "/migrations")),
            args.only or os.environ.get("ONLY_VERSION", ""),
        )
    except (MigrationError, psycopg.Error, OSError, UnicodeError) as exc:
        print(f"bootstrap migration runner failed: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
