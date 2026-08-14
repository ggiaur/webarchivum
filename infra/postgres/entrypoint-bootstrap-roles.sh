#!/usr/bin/env bash
# docker-entrypoint-initdb.d wrapper: bootstrap_roles.sql needs psql
# variables (never literal passwords in the repo), which plain .sql
# initdb scripts cannot supply. Runs once, as the image-created
# fewa_bootstrap superuser, on first cluster init only.
set -euo pipefail

: "${POSTGRES_MIGRATOR_PASSWORD:?POSTGRES_MIGRATOR_PASSWORD is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v migrator_password="$POSTGRES_MIGRATOR_PASSWORD" \
  -v app_password="$POSTGRES_APP_PASSWORD" \
  -f /docker-entrypoint-initdb.d/lib/bootstrap_roles.sql
