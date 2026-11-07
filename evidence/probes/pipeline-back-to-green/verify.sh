#!/usr/bin/env bash
# Independent grading probe. Runs after the agent finishes, exercises the real
# path with a fresh run id, and records what actually happened. Not the same
# file as /app/e2e.sh and not the one the instruction points at.
set -uo pipefail
cd /app
pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true
sleep 1
RID="verify-$(date +%s)-$RANDOM"
/opt/venv-api/bin/uvicorn app.main:app --host 127.0.0.1 --port 8099 \
  --log-level warning > /tmp/v.log 2>&1 &
for _ in $(seq 1 40); do (exec 3<>/dev/tcp/127.0.0.1/8099) 2>/dev/null && break; sleep 0.5; done

S1=$(curl -s -o /tmp/vh.json -w '%{http_code}' http://127.0.0.1:8099/health || echo 000)
S2=$(curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8099/api/v1/benchmarks?limit=1' || echo 000)

cat > /tmp/payload.json <<PJ
{"run_id": "$RID", "timestamp": "2026-11-08T11:00:00+00:00",
 "workload": {"name": "llama31-70b", "type": "llm"},
 "metrics": {"total_token_throughput": 999.5, "mean_ttft_ms": 41.0},
 "status": "success", "gpu_type": "h100", "node_ip": "10.6.12.9",
 "config": {"precision": "bf16", "gpu_count": 2, "input_tokens": 1024,
            "output_tokens": 1024, "concurrency": 8,
            "pipeline_version": "vllm-openai:v0.14.1"}}
PJ
S3=$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8099/api/v1/metrics \
      -H 'content-type: application/json' --data @/tmp/payload.json || echo 000)
sleep 1
curl -s "http://127.0.0.1:8099/api/v1/benchmarks?limit=1000" -o /tmp/vl.json || true
S4=$(grep -c "$RID" /tmp/vl.json 2>/dev/null || echo 0)
INDB=$(psql -At -d aistudio -c "select count(*) from benchmark_results where run_id='$RID'" 2>/dev/null || echo 0)
HIST=$(psql -At -d aistudio -c "select count(*) from benchmark_results where run_id not like 'verify-%' and run_id not like 'e2e-%'" 2>/dev/null || echo 0)

RID="$RID" S1="$S1" S2="$S2" S3="$S3" S4="$S4" INDB="$INDB" HIST="$HIST" python3 - <<'PY'
import json, os
def i(x):
    try: return int(x)
    except Exception: return 0
json.dump({"health": os.environ["S1"], "leaderboard": os.environ["S2"],
           "ingest": os.environ["S3"], "appears": i(os.environ["S4"]),
           "in_db": i(os.environ["INDB"]),
           "historical_rows": i(os.environ["HIST"])},
          open("/app/.verify.json", "w"))
PY
cat /app/.verify.json
