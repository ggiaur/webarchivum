"""Fail-closed ARCH-01 PostgreSQL migration runner.

Only this executable is allowed to apply versioned SQL.  It serialises runners
with a session advisory lock, validates a SHA-256 ledger, applies migrations in
version order, and separates enum-phased migration Phase A from Phase B.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import argparse
from dataclasses import dataclass
from pathlib import Path

import psycopg


LOCK_SQL = "SELECT pg_try_advisory_lock(hashtextextended('fewa:arch01:migrations', 0))"
UNLOCK_SQL = "SELECT pg_advisory_unlock(hashtextextended('fewa:arch01:migrations', 0))"
MIGRATION_RE = re.compile(r"^(?P<version>\d{3})_.+\.sql$")
MODE_RE = re.compile(r"transaction_mode=(?P<mode>[a-z_]+)")


class MigrationError(RuntimeError):
    """A migration invariant failed; caller must remediate explicitly."""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sql: str
    checksum: str
    transaction_mode: str


def load_migrations(directory: Path) -> list[Migration]:
    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_RE.match(path.name)
        if not match:
            continue
        payload = path.read_bytes()
        sql = payload.decode("utf-8")
        mode = MODE_RE.search(sql)
        migrations.append(
            Migration(
                version=match.group("version"),
                path=path.resolve(),
                sql=sql,
                checksum=hashlib.sha256(payload).hexdigest(),
                transaction_mode=mode.group("mode") if mode else "transactional",
            )
        )
    if not migrations:
        raise MigrationError(f"no migrations found in {directory}")
    if len({item.version for item in migrations}) != len(migrations):
        raise MigrationError("duplicate migration version")
    return migrations


def _without_outer_transaction(sql: str) -> str:
    """Runner owns the transaction; strip a legacy top-level BEGIN/COMMIT."""
    sql = re.sub(r"(?im)^\s*BEGIN\s*;\s*$", "", sql, count=1)
    matches = list(re.finditer(r"(?im)^\s*COMMIT\s*;\s*$", sql))
    if matches:
        start, end = matches[-1].span()
        sql = sql[:start] + sql[end:]
    return sql


def _enum_phases(migration: Migration) -> tuple[str, str]:
    marker = re.search(r"(?im)^\s*--\s*PHASE B\b.*$", migration.sql)
    if marker is None:
        raise MigrationError(f"enum_phased migration {migration.version} has no PHASE B marker")
    phase_a = migration.sql[: marker.start()]
    phase_b = _without_outer_transaction(migration.sql[marker.end() :])
    return phase_a, phase_b


def ensure_ledger(connection: psycopg.Connection) -> None:
    with connection.transaction():
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                version TEXT PRIMARY KEY,
                checksum CHAR(64) NOT NULL,
                transaction_mode TEXT NOT NULL CHECK (transaction_mode IN ('transactional', 'enum_phased')),
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


def validate_ledger(connection: psycopg.Connection, migrations: list[Migration]) -> dict[str, str]:
    known = {migration.version: migration for migration in migrations}
    rows = connection.execute(
        "SELECT version, checksum FROM public.schema_migrations ORDER BY version"
    ).fetchall()
    applied: dict[str, str] = {}
    for version, checksum in rows:
        migration = known.get(version)
        if migration is None:
            raise MigrationError(f"ledger contains unknown/out-of-order migration {version}")
        if checksum != migration.checksum:
            raise MigrationError(f"migration {version} checksum drift")
        applied[version] = checksum
    latest_applied = max(applied, default=None)
    if latest_applied is not None:
        for migration in migrations:
            if migration.version < latest_applied and migration.version not in applied:
                raise MigrationError(
                    f"out-of-order ledger: {migration.version} missing before {latest_applied}"
                )
    return applied


def record_ledger(connection: psycopg.Connection, migration: Migration) -> None:
    connection.execute(
        "INSERT INTO public.schema_migrations (version, checksum, transaction_mode) VALUES (%s, %s, %s)",
        (migration.version, migration.checksum, migration.transaction_mode),
    )


def apply_one(connection: psycopg.Connection, migration: Migration, applied: dict[str, str]) -> None:
    if migration.version in applied:
        return
    if migration.transaction_mode == "enum_phased":
        phase_a, phase_b = _enum_phases(migration)
        connection.execute(phase_a)
        with connection.transaction():
            # PostgreSQL reads this path itself for the immutable 005 checksum.
            # It is a read-only source mount shared with the database, not a
            # path inside the runner image.
            source_dir = Path(os.environ.get("MIGRATION_DB_SOURCE_DIR", "/workspace/spec/migrations"))
            connection.execute(
                "SELECT set_config('arch01.migration_source_path', %s, true)",
                (str(source_dir / migration.path.name),),
            )
            connection.execute(phase_b)
            recorded = connection.execute(
                "SELECT checksum FROM public.schema_migrations WHERE version = %s", (migration.version,)
            ).fetchone()
            if recorded is None:
                record_ledger(connection, migration)
            elif recorded[0] != migration.checksum:
                raise MigrationError(f"migration {migration.version} recorded unexpected checksum")
        return
    if migration.transaction_mode != "transactional":
        raise MigrationError(f"unsupported transaction mode {migration.transaction_mode}")
    with connection.transaction():
        connection.execute(_without_outer_transaction(migration.sql))
        record_ledger(connection, migration)


def run(database_url: str, directory: Path) -> None:
    all_migrations = load_migrations(directory)
    migrations = all_migrations
    through = os.environ.get("MIGRATION_THROUGH")
    from_version = os.environ.get("MIGRATION_FROM")
    if through and from_version:
        raise MigrationError("MIGRATION_THROUGH and MIGRATION_FROM are mutually exclusive")
    if through:
        if through > "004":
            raise MigrationError("normal runner may only run through 004 before bootstrap 005")
        migrations = [item for item in migrations if item.version <= through]
    elif from_version:
        if from_version < "006":
            raise MigrationError("normal runner may only resume from 006 after bootstrap cleanup")
        migrations = [item for item in migrations if item.version >= from_version]
    else:
        # There is deliberately no generic normal-runner path across immutable
        # 005.  Operators must make the stage boundary explicit.
        raise MigrationError("set MIGRATION_THROUGH=004 or MIGRATION_FROM=006")
    if any(item.version == "005" for item in migrations):
        raise MigrationError("migration 005 is bootstrap-executor only")
    # Keep the session advisory lock across migration transactions.  Individual
    # `connection.transaction()` blocks below provide the atomic commit point.
    with psycopg.connect(database_url, autocommit=True) as connection:
        if not connection.execute(LOCK_SQL).fetchone()[0]:
            raise MigrationError("another migration runner holds the advisory lock")
        try:
            ensure_ledger(connection)
            # The ledger is checked against the complete immutable source set;
            # the stage selector controls only which *pending* entries this
            # invocation may apply.
            applied = validate_ledger(connection, all_migrations)
            for migration in migrations:
                apply_one(connection, migration, applied)
        finally:
            connection.execute(UNLOCK_SQL)


def main() -> int:
    parser = argparse.ArgumentParser(description="ARCH-01 non-superuser migration runner")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--through", metavar="VERSION")
    selector.add_argument("--from", dest="from_version", metavar="VERSION")
    args = parser.parse_args()
    database_url = os.environ.get("MIGRATOR_DATABASE_URL")
    if not database_url or "BOOTSTRAP_DATABASE_URL" in os.environ:
        print("MIGRATOR_DATABASE_URL only is required", file=sys.stderr)
        return 2
    directory = Path(os.environ.get("MIGRATIONS_DIR", "/migrations"))
    if args.through:
        os.environ["MIGRATION_THROUGH"] = args.through
    if args.from_version:
        os.environ["MIGRATION_FROM"] = args.from_version
    try:
        run(database_url, directory)
    except (MigrationError, psycopg.Error, OSError, UnicodeError) as exc:
        print(f"migration runner failed: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
