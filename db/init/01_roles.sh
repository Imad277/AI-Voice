#!/bin/sh
# Runs once, as the container superuser, when the data volume is first created.
# Creates the two login roles VoiceOS uses. Neither is a superuser and neither has
# BYPASSRLS. Schema and tables are created later by the migrator (see
# db/migrations/), so the application role never owns a table.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v migrator_pw="$VOICEOS_MIGRATOR_PASSWORD" \
  -v app_pw="$VOICEOS_APP_PASSWORD" <<'SQL'
-- Migration/admin responsibility: owns the voiceos schema and its tables.
CREATE ROLE voiceos_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  PASSWORD :'migrator_pw';

-- Application runtime role: no ownership, no BYPASSRLS, subject to FORCE RLS.
CREATE ROLE voiceos_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
  PASSWORD :'app_pw';

REVOKE ALL ON DATABASE voiceos FROM PUBLIC;
GRANT CONNECT ON DATABASE voiceos TO voiceos_migrator, voiceos_app;
GRANT CREATE ON DATABASE voiceos TO voiceos_migrator;
SQL
