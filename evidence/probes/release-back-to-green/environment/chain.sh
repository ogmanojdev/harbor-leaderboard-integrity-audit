#!/usr/bin/env bash
# Migration-chain check. Builds a database from nothing but the revisions and
# compares the result against the ORM models.
#
# Reports which sub-check fails. It does not say why.
set -uo pipefail
cd /app
PROBE=chain_probe_$$

fail() { echo "CHAIN $1: FAIL — $2"; psql -q -c "DROP DATABASE IF EXISTS $PROBE" >/dev/null 2>&1; exit 1; }

# 1. One head. A fork means some revision claims the wrong parent.
HEADS=$(alembic heads 2>/dev/null | grep -cE '\(head\)')
[ "$HEADS" = "1" ] || fail 1 "the chain has $HEADS heads; it must have exactly one"
echo "CHAIN 1: ok — single head"

psql -q -c "DROP DATABASE IF EXISTS $PROBE" >/dev/null 2>&1
psql -q -c "CREATE DATABASE $PROBE OWNER aistudio" >/dev/null 2>&1 \
  || fail 2 "could not create a scratch database to migrate into"

# 2. The chain applies to an empty database.
POSTGRES_DATABASE=$PROBE alembic upgrade head >/tmp/chain_up.log 2>&1 \
  || fail 2 "alembic upgrade head failed on an empty database (see /tmp/chain_up.log)"
echo "CHAIN 2: ok — the chain applies to an empty database"

# 3. What the revisions build matches what the models declare.
POSTGRES_DATABASE=$PROBE python3 - <<'PY' >/tmp/chain_drift.log 2>&1
import sys
from sqlalchemy import create_engine, inspect
from app.config import get_sync_database_url
from app.database import Base
from app import models  # noqa: F401  — registers every mapper on Base.metadata

insp = inspect(create_engine(get_sync_database_url()))
live = {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names()}
missing = []
for table in Base.metadata.sorted_tables:
    if table.name not in live:
        missing.append(f"{table.name} (whole table)")
        continue
    for col in table.columns:
        if col.name not in live[table.name]:
            missing.append(f"{table.name}.{col.name}")
if missing:
    print("declared by the models, never created by a revision:")
    for m in sorted(missing):
        print("  " + m)
    sys.exit(1)
print("no drift")
PY
[ $? -eq 0 ] || fail 3 "the schema the revisions build does not match the models (see /tmp/chain_drift.log)"
echo "CHAIN 3: ok — revisions and models agree"

# 4. Every revision can be undone and redone.
POSTGRES_DATABASE=$PROBE alembic downgrade base >/tmp/chain_down.log 2>&1 \
  || fail 4 "alembic downgrade base failed (see /tmp/chain_down.log)"
POSTGRES_DATABASE=$PROBE alembic upgrade head >>/tmp/chain_down.log 2>&1 \
  || fail 4 "the chain did not re-apply after a downgrade (see /tmp/chain_down.log)"
echo "CHAIN 4: ok — the chain round-trips"

psql -q -c "DROP DATABASE IF EXISTS $PROBE" >/dev/null 2>&1
echo
echo "CHAIN GREEN"
