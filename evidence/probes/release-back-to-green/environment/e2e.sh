#!/usr/bin/env bash
# End-to-end check for the ingest -> leaderboard pipeline.
# Reports which stage fails. It does not say why.
set -uo pipefail
cd /app
pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true
sleep 1
RUN_ID="e2e-$(date +%s)"
/opt/venv-api/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 \
  --log-level warning > /tmp/api.log 2>&1 &
for _ in $(seq 1 40); do
  (exec 3<>/dev/tcp/127.0.0.1/8001) 2>/dev/null && break; sleep 0.5
done

fail() { echo "STAGE $1: FAIL — $2"; echo; echo "--- last 25 lines of /tmp/api.log"; tail -25 /tmp/api.log; exit 1; }

code=$(curl -s -o /tmp/h.json -w '%{http_code}' http://127.0.0.1:8001/health || echo 000)
[ "$code" = "200" ] || fail 1 "the API did not come up healthy (HTTP $code)"
grep -q '"database":"ok"' /tmp/h.json || fail 1 "the API is up but reports its database unreachable"
echo "STAGE 1: ok — API healthy"

code=$(curl -s -o /tmp/b.json -w '%{http_code}' 'http://127.0.0.1:8001/api/v1/benchmarks?limit=1' || echo 000)
[ "$code" = "200" ] || fail 2 "GET /api/v1/benchmarks returned HTTP $code"
echo "STAGE 2: ok — leaderboard route responds"

code=$(curl -s -o /tmp/i.json -w '%{http_code}' -X POST http://127.0.0.1:8001/api/v1/metrics \
  -H 'content-type: application/json' -d "{
  \"run_id\": \"$RUN_ID\", \"timestamp\": \"2026-11-08T10:00:00+00:00\",
  \"workload\": {\"name\": \"llama31-70b\", \"type\": \"llm\"},
  \"metrics\": {\"total_token_throughput\": 1234.5, \"mean_ttft_ms\": 42.0,
                \"parallelism\": {\"tensor_parallel_size\": 2, \"pipeline_parallel_size\": 1}},
  \"status\": \"success\", \"gpu_type\": \"h100\", \"node_ip\": \"10.6.12.9\",
  \"config\": {\"precision\": \"bf16\", \"gpu_count\": 2, \"input_tokens\": 1024,
               \"output_tokens\": 1024, \"concurrency\": 8,
               \"pipeline_version\": \"vllm-openai:v0.14.1\"}}" || echo 000)
[ "$code" = "202" ] || fail 3 "POST /api/v1/metrics returned HTTP $code (expected 202)"
echo "STAGE 3: ok — ingest accepted the run"

sleep 1
code=$(curl -s -o /tmp/l.json -w '%{http_code}' "http://127.0.0.1:8001/api/v1/benchmarks?limit=1000" || echo 000)
[ "$code" = "200" ] || fail 4 "GET /api/v1/benchmarks returned HTTP $code after ingest"
grep -q "$RUN_ID" /tmp/l.json || fail 4 "the run was accepted by ingest but does not appear on the leaderboard"
echo "STAGE 4: ok — the ingested run appears on the leaderboard"
echo
echo "PIPELINE GREEN"
