# Single-container environment: PostgreSQL 16 and the application source live
# together, so the task needs no inter-service networking and can run under
# Harbor's strictest policy, network_mode = "no-network".
#
# The database is initialised and seeded at BUILD time, so every run starts
# from a byte-identical data directory and nothing is fetched at run time.
FROM postgres:16.4-bookworm

# PGDATA is moved off /var/lib/postgresql/data on purpose: the upstream image
# declares that path as a VOLUME, and writes made to a declared volume during
# build are discarded. Seeding at build time therefore requires a path that is
# not a volume.
ENV PGDATA=/var/lib/pgdata \
    POSTGRES_DB=aistudio \
    POSTGRES_USER=aistudio \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      python3-psycopg2 \
      jq \
 && rm -rf /var/lib/apt/lists/*

COPY seed/schema.sql /opt/seed/schema.sql
COPY seed/seed.sql   /opt/seed/seed.sql

# Initialise the cluster and load the corpus during the build.
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

# Application source, vendored from corespan/aistudio-server (Apache-2.0).
# See app/VENDORED_COMMIT for the exact pinned revision.
COPY app /app/app
RUN mkdir -p /app/audit && chmod 0777 /app/audit

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

ENV PGHOST=/var/run/postgresql \
    PGUSER=aistudio \
    PGDATABASE=aistudio

WORKDIR /app
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
