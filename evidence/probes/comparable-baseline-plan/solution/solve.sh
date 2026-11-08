#!/bin/bash
# Oracle. The platform's own rule, applied exactly.
#
#   mcp-server/app/services/platform_api.py :: comparable_results
#     peers share model_name, gpu_type, concurrency, precision, input_tokens,
#     output_tokens and workload_type, must have the same gpu_count, must have
#     status success, must have a non-null total_token_throughput, and must not
#     be the target run itself - so a run needs 3 peers besides itself, i.e. a
#     configuration group needs 4 eligible runs.
#
# So the floor is per (those seven fields + concurrency) group, counting only
# rows that satisfy the eligibility clause. One sweep adds one eligible run to
# every concurrency it covers, so a group of configurations differing only in
# concurrency needs max(deficit) sweeps, not sum(deficit).
set -euo pipefail

python3 - <<'PY'
import json, subprocess
from collections import defaultdict

SQL = ("select model_name, gpu_type, gpu_count, precision, input_tokens, "
       "output_tokens, coalesce(workload_type,''), concurrency, "
       "count(*) filter (where status='success' and total_token_throughput is not null) "
       "from benchmark_results "
       "group by 1,2,3,4,5,6,7,8")
r = subprocess.run(["psql", "-At", "-F", "\x1f", "-d", "aistudio", "-c", SQL],
                   capture_output=True, text=True, check=True)

TARGET = 4
deficit = defaultdict(dict)          # 7-tuple -> {concurrency: how many more}
for line in r.stdout.strip().split("\n"):
    f = line.split("\x1f")
    tup = (f[0], f[1], int(f[2]), f[3], int(f[4]), int(f[5]), f[6])
    c, elig = int(f[7]), int(f[8])
    if elig < TARGET:
        deficit[tup][c] = TARGET - elig

sweeps = []
for tup, per_c in deficit.items():
    # Sweep i covers every concurrency still short after i previous sweeps.
    for i in range(max(per_c.values())):
        levels = sorted(c for c, d in per_c.items() if d > i)
        sweeps.append({
            "model_name": tup[0], "gpu_type": tup[1], "gpu_count": tup[2],
            "precision": tup[3], "input_tokens": tup[4], "output_tokens": tup[5],
            "workload_type": tup[6], "concurrencies": levels,
        })

json.dump({"sweeps": sweeps}, open("/app/plan.json", "w"), indent=2)
print("sweeps planned:", len(sweeps))
print("configurations below the floor:", sum(len(v) for v in deficit.values()))
PY

python3 /app/validate_plan.py

cat > /app/plan_notes.md <<'MD'
- The rule is `comparable_results` in `mcp-server/app/services/platform_api.py`, pinned by `mcp-server/tests/test_platform_api.py::test_comparable_results_keep_only_the_identical_config`: peers share model_name, gpu_type, concurrency, precision, input_tokens, output_tokens and workload_type, must match on gpu_count, and must have status success with a non-null total_token_throughput.
- Counting: the floor applies per (those seven fields + concurrency) group, and only rows satisfying the eligibility clause count. Counting all rows understates the shortfall by 19 groups; checking status but not the null metric still understates it by 10.
- Budget: one sweep adds one eligible run at every concurrency it covers, so a family of configurations differing only in concurrency needs max(deficit) sweeps rather than sum(deficit). That is 14 sweeps against 67 short configurations.
MD
