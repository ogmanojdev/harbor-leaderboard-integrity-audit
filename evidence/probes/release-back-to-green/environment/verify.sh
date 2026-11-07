#!/usr/bin/env bash
# Independent grading probe. Runs in the agent's container after the agent
# phase, re-derives all three gates from scratch, and records only numbers.
# Deliberately shares no file with /app/e2e.sh or /app/chain.sh: weakening
# either of those buys nothing here.
set -uo pipefail
cd /app

# ── Gate: suite ───────────────────────────────────────────────────────────────
pytest -q -p no:cacheprovider -c /opt/pristine-pytest.ini /opt/pristine-tests/ >/tmp/v_suite.log 2>&1
SP=$(grep -oE '[0-9]+ passed'  /tmp/v_suite.log | tail -1 | grep -oE '[0-9]+' || echo 0)
SF=$(grep -oE '[0-9]+ failed'  /tmp/v_suite.log | tail -1 | grep -oE '[0-9]+' || echo 0)
SE=$(grep -cE '^(ERROR|ImportError)' /tmp/v_suite.log || echo 0)

# ── Gate: live path ───────────────────────────────────────────────────────────
pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true
sleep 1
RID="grade-$(date +%s)-$RANDOM"
uvicorn app.main:app --host 127.0.0.1 --port 8097 --log-level warning >/tmp/v_api.log 2>&1 &
for _ in $(seq 1 40); do (exec 3<>/dev/tcp/127.0.0.1/8097) 2>/dev/null && break; sleep 0.5; done

H=$(curl -s -o /tmp/v_h.json -w '%{http_code}' http://127.0.0.1:8097/health 2>/dev/null || echo 0)
L=$(curl -s -o /dev/null  -w '%{http_code}' 'http://127.0.0.1:8097/api/v1/benchmarks?limit=1' 2>/dev/null || echo 0)
cat > /tmp/v_payload.json <<PJ
{"run_id": "$RID", "timestamp": "2026-11-09T11:00:00+00:00",
 "workload": {"name": "llama31-70b", "type": "llm"},
 "metrics": {"total_token_throughput": 999.5, "mean_ttft_ms": 41.0},
 "status": "success", "gpu_type": "H100", "node_ip": "10.6.12.9",
 "config": {"precision": "bf16", "gpu_count": 2, "input_tokens": 1024,
            "output_tokens": 1024, "concurrency": 8,
            "pipeline_version": "vllm-openai:v0.14.1"}}
PJ
I=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8097/api/v1/metrics \
      -H 'content-type: application/json' --data @/tmp/v_payload.json 2>/dev/null || echo 0)
sleep 1
curl -s "http://127.0.0.1:8097/api/v1/benchmarks?limit=1000" -o /tmp/v_l.json 2>/dev/null || true
A=$(grep -c "$RID" /tmp/v_l.json 2>/dev/null || echo 0)
DB=$(psql -At -d aistudio -c "select count(*) from benchmark_results where run_id='$RID'" 2>/dev/null || echo 0)
# gpu_type must be normalised: the payload above sends 'H100'
GL=$(psql -At -d aistudio -c "select count(*) from benchmark_results where run_id='$RID' and gpu_type='h100'" 2>/dev/null || echo 0)
HIST=$(psql -At -d aistudio -c "select count(*) from benchmark_results where run_id not like 'grade-%' and run_id not like 'verify-%' and run_id not like 'e2e-%'" 2>/dev/null || echo 0)
pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true

# ── Gate: chain ───────────────────────────────────────────────────────────────
PROBE=grade_probe_$$
HEADS=$(alembic heads 2>/dev/null | grep -cE '\(head\)' || echo 0)
psql -q -c "DROP DATABASE IF EXISTS $PROBE" >/dev/null 2>&1
psql -q -c "CREATE DATABASE $PROBE OWNER aistudio" >/dev/null 2>&1
POSTGRES_DATABASE=$PROBE alembic upgrade head >/tmp/v_chain.log 2>&1 && UP=1 || UP=0
DRIFT=$(POSTGRES_DATABASE=$PROBE python3 - 2>/dev/null <<'PY'
try:
    from sqlalchemy import create_engine, inspect
    from app.config import get_sync_database_url
    from app.database import Base
    from app import models  # noqa: F401
    insp = inspect(create_engine(get_sync_database_url()))
    live = {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names()}
    n = 0
    for table in Base.metadata.sorted_tables:
        if table.name not in live:
            n += 1
            continue
        n += sum(1 for c in table.columns if c.name not in live[table.name])
    print(n)
except Exception:
    print(999)
PY
)
POSTGRES_DATABASE=$PROBE alembic downgrade base >/tmp/v_down.log 2>&1 \
  && POSTGRES_DATABASE=$PROBE alembic upgrade head >>/tmp/v_down.log 2>&1 && RT=1 || RT=0
psql -q -c "DROP DATABASE IF EXISTS $PROBE" >/dev/null 2>&1

FX=0
[ -f /app/fixes.md ] && FX=$(wc -c < /app/fixes.md | tr -d ' ')

# Hash both copies of the suite. check.py holds the expected value and lives in
# the verifier image, out of the agent's reach.
_sha_of() { python3 -c "
import hashlib, pathlib, sys
d = pathlib.Path(sys.argv[1]); h = hashlib.sha256()
for f in sorted(d.rglob(chr(42)+chr(46)+chr(112)+chr(121))):
    h.update(f.relative_to(d).as_posix().encode()); h.update(f.read_bytes())
print(h.hexdigest())" "$1"; }
SHA_APP=$(_sha_of /app/tests)
SHA_PRI=$(_sha_of /opt/pristine-tests)

SHA_APP="$SHA_APP" SHA_PRI="$SHA_PRI" SP="$SP" SF="$SF" SE="$SE" H="$H" L="$L" I="$I" A="$A" DB="$DB" GL="$GL" HIST="$HIST" \
HEADS="$HEADS" UP="$UP" DRIFT="${DRIFT:-999}" RT="$RT" FX="$FX" python3 - <<'PY'
import json, os
def i(x):
    try: return int(str(x).strip())
    except Exception: return 0
keys = ["SP","SF","SE","H","L","I","A","DB","GL","HIST","HEADS","UP","DRIFT","RT","FX"]
out = {k.lower(): i(os.environ.get(k, 0)) for k in keys}
out["sha_app"] = os.environ.get("SHA_APP", "").strip()
out["sha_pristine"] = os.environ.get("SHA_PRI", "").strip()
json.dump(out, open("/app/.verify.json", "w"), indent=2)
print(json.dumps(out))
PY
