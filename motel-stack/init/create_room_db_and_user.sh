#!/usr/bin/env bash
set -euo pipefail

# This script runs inside the postgres container to create two databases and users
# Usage: docker compose exec -T postgres /bin/sh -c "/scripts/create_room_db_and_user.sh"

psql -v ON_ERROR_STOP=1 --username "postgres" <<-SQL
  -- Create motel POS user and DB if they do not exist
  DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${MOTEL_POSTGRES_USER}') THEN
      CREATE USER ${MOTEL_POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
    END IF;
  END $$;
  DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${MOTEL_POSTGRES_DB}') THEN
      CREATE DATABASE ${MOTEL_POSTGRES_DB} OWNER ${MOTEL_POSTGRES_USER};
    END IF;
  END $$;

  -- Create room pulse user and DB
  DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${ROOM_POSTGRES_USER}') THEN
      CREATE USER ${ROOM_POSTGRES_USER} WITH PASSWORD '${ROOM_POSTGRES_PASSWORD}';
    END IF;
  END $$;
  DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${ROOM_POSTGRES_DB}') THEN
      CREATE DATABASE ${ROOM_POSTGRES_DB} OWNER ${ROOM_POSTGRES_USER};
    END IF;
  END $$;

  GRANT ALL PRIVILEGES ON DATABASE ${ROOM_POSTGRES_DB} TO ${ROOM_POSTGRES_USER};
  GRANT ALL PRIVILEGES ON DATABASE ${MOTEL_POSTGRES_DB} TO ${MOTEL_POSTGRES_USER};
SQL

echo "Ensured databases ${MOTEL_POSTGRES_DB}, ${ROOM_POSTGRES_DB} and users ${MOTEL_POSTGRES_USER}, ${ROOM_POSTGRES_USER} exist"
