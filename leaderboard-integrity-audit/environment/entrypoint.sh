#!/usr/bin/env bash
# Bring up the three loopback services, then hand control to the harness.
#
# Using ENTRYPOINT rather than CMD means these start even when the harness
# overrides the container command. Each wait is bounded and failure is loud:
# an agent handed a half-started environment would fail for reasons that say
# nothing about its capability, which is exactly the outcome to avoid.
set -euo pipefail

log() { echo "[entrypoint] $*" >&2; }

wait_for_port() {
  local port="$1" name="$2" tries="${3:-120}"
  for _ in $(seq 1 "$tries"); do
    if (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null; then
      exec 3<&- 2>/dev/null || true
      return 0
    fi
    sleep 0.5
  done
  log "FATAL: ${name} did not open port ${port}"
  return 1
}

# ── PostgreSQL ───────────────────────────────────────────────────────────────
if ! su postgres -c "pg_ctl -D ${PGDATA} status" >/dev/null 2>&1; then
  mkdir -p /var/run/postgresql
  chown postgres:postgres /var/run/postgresql
  su postgres -c "pg_ctl -D ${PGDATA} -o '-c listen_addresses=127.0.0.1' -w start" >/dev/null
fi
for _ in $(seq 1 120); do
  pg_isready -q -h 127.0.0.1 -U aistudio -d aistudio && break
  sleep 0.5
done
pg_isready -q -h 127.0.0.1 -U aistudio -d aistudio || { log "FATAL: postgres not ready"; exit 1; }
log "postgres ready"

# ── aistudio-server REST API ─────────────────────────────────────────────────
if ! (exec 3<>/dev/tcp/127.0.0.1/8001) 2>/dev/null; then
  ( cd /app && exec /opt/venv-api/bin/uvicorn app.main:app \
      --host 127.0.0.1 --port 8001 --log-level warning ) \
    >/var/log/aistudio-api.log 2>&1 &
fi
wait_for_port 8001 "aistudio-server API" || { tail -40 /var/log/aistudio-api.log >&2; exit 1; }
log "api ready on 127.0.0.1:8001"

# ── aistudio MCP tool server ─────────────────────────────────────────────────
if ! (exec 3<>/dev/tcp/127.0.0.1/8081) 2>/dev/null; then
  ( cd /opt/mcp-server && exec /opt/venv-mcp/bin/python -m app.mcp_server ) \
    >/var/log/aistudio-mcp.log 2>&1 &
fi
wait_for_port 8081 "aistudio-mcp" || { tail -40 /var/log/aistudio-mcp.log >&2; exit 1; }
log "mcp ready on 127.0.0.1:8081/mcp"

exec "$@"
