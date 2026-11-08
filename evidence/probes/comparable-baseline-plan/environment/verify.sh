#!/usr/bin/env bash
# Independent grading probe. Re-derives peer coverage from the database and the
# submitted plan. Shares no code with /app/validate_plan.py.
set -uo pipefail
cd /app
python3 - <<'PY'
import json, os, subprocess

ALLOWED = {1, 2, 4, 8, 16, 32, 64, 128}
BUDGET = int(os.environ.get("SWEEP_BUDGET", "23"))
# Every run needs 3 peers OTHER than itself, so a group needs 4 eligible runs.
TARGET = 4
KEY = ("model_name", "gpu_type", "gpu_count", "precision",
       "input_tokens", "output_tokens", "workload_type")

def rows():
    sql = ("select model_name, gpu_type, gpu_count, precision, input_tokens, "
           "output_tokens, coalesce(workload_type,''), concurrency, "
           "count(*) filter (where status='success' and total_token_throughput is not null) "
           "from benchmark_results group by 1,2,3,4,5,6,7,8")
    r = subprocess.run(["psql", "-At", "-F", "\x1f", "-d", "aistudio", "-c", sql],
                       capture_output=True, text=True)
    out = {}
    for line in r.stdout.strip().split("\n"):
        if not line:
            continue
        f = line.split("\x1f")
        grp = (f[0], f[1], int(f[2]), f[3], int(f[4]), int(f[5]), f[6])
        out[(grp, int(f[7]))] = int(f[8])
    return out

res = {"plan_parses": 0, "schema_valid": 0, "known_entities": 0,
       "allowed_concurrencies": 0, "coverage": 0, "within_budget": 0,
       "n_sweeps": 0, "groups_total": 0, "groups_short": 0, "worst_shortfall": 0}

groups = rows()
res["groups_total"] = len(groups)

plan = None
try:
    plan = json.load(open("/app/plan.json"))
    res["plan_parses"] = 1
except Exception:
    pass

sweeps = []
if isinstance(plan, dict) and isinstance(plan.get("sweeps"), list):
    sweeps = [s for s in plan["sweeps"] if isinstance(s, dict)]
    res["schema_valid"] = 1 if len(sweeps) == len(plan["sweeps"]) and all(
        all(k in s for k in KEY) and isinstance(s.get("concurrencies"), list) and s["concurrencies"]
        for s in sweeps) else 0
res["n_sweeps"] = len(sweeps)
res["within_budget"] = 1 if (sweeps and len(sweeps) <= BUDGET) else 0

known_models = {g[0][0] for g in groups}
known_gpus = {g[0][1] for g in groups}
if sweeps:
    res["known_entities"] = 1 if all(
        s.get("model_name") in known_models and s.get("gpu_type") in known_gpus for s in sweeps) else 0
    res["allowed_concurrencies"] = 1 if all(
        all(c in ALLOWED for c in s.get("concurrencies", [])) for s in sweeps) else 0

# Apply the plan: each sweep adds one eligible run per concurrency it covers.
added = {}
for s in sweeps:
    try:
        grp = (s["model_name"], s["gpu_type"], int(s["gpu_count"]), s["precision"],
               int(s["input_tokens"]), int(s["output_tokens"]), s.get("workload_type") or "")
    except Exception:
        continue
    for c in s.get("concurrencies", []):
        added[(grp, c)] = added.get((grp, c), 0) + 1

short = 0
worst = 0
for k, have in groups.items():
    after = have + added.get(k, 0)
    if after < TARGET:
        short += 1
        worst = max(worst, TARGET - after)
res["groups_short"] = short
res["worst_shortfall"] = worst
res["coverage"] = 1 if short == 0 else 0

json.dump(res, open("/app/.verify.json", "w"), indent=2)
print(json.dumps(res))
PY
