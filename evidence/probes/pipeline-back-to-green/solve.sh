#!/bin/bash
# Oracle: four defects, each only visible once the one before it is fixed.
set -euo pipefail

# 1. The DSN names a driver that is not installed, so the engine cannot be built.
sed -i 's|postgresql+psycopg_async|postgresql+asyncpg|' /app/app/config.py

# 2. The database predates the mean_e2el_ms migration; every query touching
#    benchmark_results fails until the column exists.
psql -v ON_ERROR_STOP=1 -d aistudio -c \
  "ALTER TABLE benchmark_results ADD COLUMN IF NOT EXISTS mean_e2el_ms DOUBLE PRECISION;"

# 3. The upsert targets (run_id) alone, which is not a unique constraint, so
#    every ingest raises.
sed -i 's|index_elements=\["run_id"\],|index_elements=["run_id", "sub_run_index"],|' \
  /app/app/routers/ingest.py

# 4. A stale filter hides every row whose server_name is NULL, which is every
#    row ingest creates unless the runner supplies one.
python3 - <<'PY'
import pathlib
p = pathlib.Path("/app/app/routers/results.py"); s = p.read_text()
s = s.replace("    # hide rows that never completed hardware validation\n"
              "    conditions.append(BenchmarkResult.server_name.isnot(None))\n", "")
p.write_text(s)
PY

/app/e2e.sh

/app/e2e.sh

cat > /app/fixes.md <<MD
- config.py: DSN named an uninstalled driver (psycopg_async); restored asyncpg.
- database: mean_e2el_ms column missing; added it.
- ingest.py: upsert targeted (run_id) which is not unique; restored (run_id, sub_run_index).
- results.py: stale filter hid rows with NULL server_name, i.e. every newly ingested row; removed.
MD
