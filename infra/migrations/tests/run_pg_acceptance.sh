#!/usr/bin/env bash
# Destructive isolated-DB acceptance for R1.  Do not point these variables at
# production.  PostgreSQL itself must have the immutable source mounted at
# /fixed/read-only/migrations, read-only; the bootstrap executor uses no
# caller-selected server path.
set -euo pipefail

: "${BOOTSTRAP_DATABASE_URL:?required}" "${MIGRATOR_DATABASE_URL:?required}" "${APP_DATABASE_URL:?required}"
: "${MIGRATOR_PASSWORD:?required}" "${APP_PASSWORD:?required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
psql "$BOOTSTRAP_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
  -v migrator_password="$MIGRATOR_PASSWORD" -v app_password="$APP_PASSWORD" \
  -f "$ROOT/infra/postgres/bootstrap_roles.sql"

MIGRATOR_DATABASE_URL="$MIGRATOR_DATABASE_URL" MIGRATION_THROUGH=004 \
  docker run --rm arch01-r1-runner
BOOTSTRAP_DATABASE_URL="$BOOTSTRAP_DATABASE_URL" ONLY_VERSION=005 \
  docker run --rm arch01-r1-bootstrap
MIGRATOR_DATABASE_URL="$MIGRATOR_DATABASE_URL" MIGRATION_FROM=006 \
  docker run --rm arch01-r1-runner

psql "$MIGRATOR_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT version, checksum FROM schema_migrations WHERE version IN ('005','006') ORDER BY version"
psql "$MIGRATOR_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT pg_has_role('fewa_migrator','pg_read_server_files','member'),
          pg_has_role('fewa_app','pg_read_server_files','member')"
psql "$MIGRATOR_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT stage, result FROM arch01_bootstrap_operations ORDER BY started_at"
psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT rolsuper, rolbypassrls, rolreplication FROM pg_roles WHERE rolname=current_user"

for statement in \
  "SET session_replication_role = replica" \
  "ALTER TABLE public.archived_snapshots DISABLE TRIGGER ALL" \
  "ALTER TABLE public.archived_snapshots ADD COLUMN arch01_must_not_exist integer" \
  "CREATE TABLE public.arch01_must_not_exist (id integer)"; do
  if psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "$statement"; then
    echo "R1 acceptance failure: app command unexpectedly succeeded: $statement" >&2
    exit 1
  fi
done

if psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT pg_read_binary_file('/fixed/read-only/migrations/005_arch_01_pipeline.sql')"; then
  echo "R1 acceptance failure: app can read server file" >&2
  exit 1
fi
if psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT * FROM public.arch01_bootstrap_operations"; then
  echo "R1 acceptance failure: app can read bootstrap audit" >&2
  exit 1
fi
