#!/usr/bin/env bash
# Start the local PostgreSQL cluster, then hand control to whatever command the
# harness runs. Using ENTRYPOINT (rather than CMD) means the database comes up
# even when the harness overrides the container command.
set -euo pipefail

if ! su postgres -c "pg_ctl -D ${PGDATA} status" >/dev/null 2>&1; then
  mkdir -p /var/run/postgresql
  chown postgres:postgres /var/run/postgresql
  # Unix socket only: the task requires no TCP listener and no network.
  su postgres -c "pg_ctl -D ${PGDATA} -o '-c listen_addresses=' -w start" >/dev/null
fi

# Block until the server accepts connections, so the agent never races the DB.
for _ in $(seq 1 60); do
  if pg_isready -q -h /var/run/postgresql -U aistudio -d aistudio; then break; fi
  sleep 0.5
done

exec "$@"
