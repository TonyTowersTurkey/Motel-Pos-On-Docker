#!/usr/bin/env bash
set -euo pipefail

# This script runs inside the postgres container to create two databases and users
# Usage: docker compose exec -T postgres /bin/sh -c "/scripts/create_room_db_and_user.sh"

psql -v ON_ERROR_STOP=1 --username "${PGUSER:-postgres}" \
  -v motel_user="${MOTEL_POSTGRES_USER}" \
  -v motel_db="${MOTEL_POSTGRES_DB}" \
  -v room_user="${ROOM_POSTGRES_USER}" \
  -v room_db="${ROOM_POSTGRES_DB}" \
  -v postgres_password="${POSTGRES_PASSWORD}" \
  -v room_password="${ROOM_POSTGRES_PASSWORD}" <<-'SQL'
  SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'motel_user', :'postgres_password')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'motel_user') \gexec
  SELECT format('ALTER ROLE %I WITH PASSWORD %L', :'motel_user', :'postgres_password') \gexec

  SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'room_user', :'room_password')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'room_user') \gexec
  SELECT format('ALTER ROLE %I WITH PASSWORD %L', :'room_user', :'room_password') \gexec

  SELECT format('CREATE DATABASE %I OWNER %I', :'motel_db', :'motel_user')
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'motel_db') \gexec
  SELECT format('CREATE DATABASE %I OWNER %I', :'room_db', :'room_user')
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'room_db') \gexec

  SELECT format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', :'motel_db', :'motel_user') \gexec
  SELECT format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', :'room_db', :'room_user') \gexec
SQL

echo "Ensured databases ${MOTEL_POSTGRES_DB}, ${ROOM_POSTGRES_DB} and users ${MOTEL_POSTGRES_USER}, ${ROOM_POSTGRES_USER} exist"
