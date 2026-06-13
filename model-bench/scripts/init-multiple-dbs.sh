#!/bin/bash
# Creates additional databases listed in POSTGRES_MULTIPLE_DATABASES (comma-separated).
# The primary database (POSTGRES_DB) is already created by the postgres entrypoint.
set -e

if [ -z "$POSTGRES_MULTIPLE_DATABASES" ]; then
  exit 0
fi

for db in $(echo "$POSTGRES_MULTIPLE_DATABASES" | tr ',' ' '); do
  if [ "$db" != "$POSTGRES_DB" ]; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
      SELECT 'CREATE DATABASE $db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
      GRANT ALL PRIVILEGES ON DATABASE $db TO $POSTGRES_USER;
EOSQL
  fi
done
