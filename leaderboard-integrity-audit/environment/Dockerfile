# Single-container environment for the leaderboard-integrity-audit task.
#
# Three services on loopback only: PostgreSQL 16, the aistudio-server REST API,
# and the aistudio MCP tool server. Nothing listens on an external interface and
# nothing is fetched at run time, so the task runs under Harbor's strictest
# policy, network_mode = "no-network" (which still provides a loopback device).
#
# Application source and MCP server are vendored from corespan/aistudio-server
# (Apache-2.0) at the commit in VENDORED_COMMIT.
FROM postgres:16.4-bookworm

# PGDATA is moved off /var/lib/postgresql/data deliberately: the upstream image
# declares that path a VOLUME, and writes to a declared volume during build are
# discarded. Seeding at build time needs a path that is not a volume.
ENV PGDATA=/var/lib/pgdata \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip python3-psycopg2 \
      jq curl ca-certificates iproute2 iputils-ping openssh-client git \
      procps xz-utils \
 && rm -rf /var/lib/apt/lists/*

# Two virtualenvs on purpose: the API and the MCP server pin conflicting
# versions of shared dependencies (anyio 4.14.2 vs 4.15.1), so a single
# environment cannot satisfy both lock files.
COPY requirements-api.lock.txt /opt/requirements-api.lock.txt
RUN python3 -m venv /opt/venv-api \
 && /opt/venv-api/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv-api/bin/pip install --no-cache-dir --require-hashes \
      -r /opt/requirements-api.lock.txt

COPY requirements-mcp.lock.txt /opt/requirements-mcp.lock.txt
RUN python3 -m venv /opt/venv-mcp \
 && /opt/venv-mcp/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv-mcp/bin/pip install --no-cache-dir --require-hashes \
      -r /opt/requirements-mcp.lock.txt

# ── Database, initialised and seeded during the build ────────────────────────
COPY seed/schema.sql /opt/seed/schema.sql
COPY seed/seed.sql   /opt/seed/seed.sql
RUN set -eux; \
    mkdir -p "$PGDATA" /var/run/postgresql; \
    chown -R postgres:postgres "$PGDATA" /var/run/postgresql /opt/seed; \
    su postgres -c "initdb -D $PGDATA --encoding=UTF8 --locale=C"; \
    su postgres -c "pg_ctl -D $PGDATA -o '-c listen_addresses=' -w start"; \
    su postgres -c "createuser --superuser aistudio"; \
    su postgres -c "createdb --owner=aistudio aistudio"; \
    su postgres -c "psql -v ON_ERROR_STOP=1 -d aistudio -f /opt/seed/schema.sql"; \
    su postgres -c "psql -v ON_ERROR_STOP=1 -d aistudio -f /opt/seed/seed.sql"; \
    su postgres -c "pg_ctl -D $PGDATA -m fast -w stop"; \
    rm -rf /opt/seed

# ── Application source (the agent reads and patches this) ────────────────────
COPY app /app/app
COPY catalog.json /app/catalog.json
COPY LICENSE /app/LICENSE
COPY NOTICE /app/NOTICE
COPY VENDORED_COMMIT /app/VENDORED_COMMIT
RUN mkdir -p /app/audit && chmod 0777 /app/audit

# ── MCP tool server ──────────────────────────────────────────────────────────
COPY mcp-server/app /opt/mcp-server/app
COPY gateway/jwks.json /opt/gateway/jwks.json

# ── Agent harness, baked in ─────────────────────────────────────────────────
# The task runs with no network, so Claude Code cannot bootstrap itself at run
# time: its installer would apt-get nodejs and npm, and fail. Harbor skips that
# step entirely when `claude` is already on PATH, so it is installed here while
# the build still has network. That also pins the harness into the image rather
# than fetching a different version on every run.
#
# Debian bookworm ships Node 18; the CLI needs >= 22, so an official binary is
# used. The architecture is resolved at build time so the image builds on both
# amd64 and arm64.
ARG NODE_VERSION=22.23.4
ARG CLAUDE_CODE_VERSION=2.1.317
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) node_arch='x64' ;; \
      arm64) node_arch='arm64' ;; \
      *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz" \
      -o /tmp/node.tar.xz; \
    mkdir -p /opt/node; \
    tar -xJf /tmp/node.tar.xz -C /opt/node --strip-components=1; \
    rm /tmp/node.tar.xz; \
    ln -sf /opt/node/bin/node /usr/local/bin/node; \
    ln -sf /opt/node/bin/npm /usr/local/bin/npm; \
    ln -sf /opt/node/bin/npx /usr/local/bin/npx; \
    node --version; \
    npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"; \
    ln -sf /opt/node/bin/claude /usr/local/bin/claude; \
    claude --version

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# aistudio-server API
ENV POSTGRES_HOST=127.0.0.1 \
    POSTGRES_PORT=5432 \
    POSTGRES_USERNAME=aistudio \
    POSTGRES_DATABASE=aistudio \
    PORT=8001 \
    PYTHONPATH=/app

# MCP tool server. Verification is mandatory (the server refuses to start with
# no JWKS), so the public key ships in the image and the matching token is
# supplied to the agent by Harbor. MCP_JWT_MAX_LIFETIME_SECONDS=0 lifts the
# one-day cap: a token that expired would make a rerun fail for reasons that
# have nothing to do with the agent.
ENV AISTUDIO_API_URL=http://127.0.0.1:8001 \
    MCP_HOST=127.0.0.1 \
    MCP_PORT=8081 \
    MCP_JWKS_FILE=/opt/gateway/jwks.json \
    MCP_JWT_ISSUER=aistudio \
    MCP_JWT_AUDIENCE=mcp:aistudio \
    MCP_JWT_MAX_LIFETIME_SECONDS=0 \
    MCP_WRITES_ENABLED=false \
    MCP_ENV_FILE=/opt/mcp-server/.env \
    REPO_PATH=/app \
    READABLE_ROOTS=/app \
    NODE_ALLOWED_CIDRS= \
    MCP_ALLOWED_HOSTS=127.0.0.1:8081,localhost:8081,127.0.0.1,localhost

RUN touch /opt/mcp-server/.env

# Client-facing socket for psql convenience.
ENV PGHOST=127.0.0.1 PGUSER=aistudio PGDATABASE=aistudio

WORKDIR /app
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
