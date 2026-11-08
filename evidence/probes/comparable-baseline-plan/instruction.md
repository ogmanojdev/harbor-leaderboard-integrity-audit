# Plan the sweeps that make the leaderboard trustworthy again

This container runs the AIStudio benchmarking backend: a FastAPI service and
worker in `/app/app`, an MCP tool server in `/app/mcp-server`, its published
contract in `/app/api_contract/API_CONTRACT.md`, operator documentation in
`/app/docs`, and a PostgreSQL database holding the historical benchmark corpus.

The leaderboard reports each benchmark run against its **comparable peers** —
past runs the platform considers to be measuring the same thing. A run with too
few comparable peers is reported, but the comparison behind it is not worth
much.

Engineering has set a floor: **every benchmark run in the corpus must have at
least three peers, other than itself, that this platform would accept as
comparable to it.** Many runs are currently below that floor.

## Your deliverable

Write `/app/plan.json`: the sweeps to schedule in order to bring every
configuration up to the floor.

```json
{
  "sweeps": [
    {
      "model_name": "llama31-70b",
      "gpu_type": "h100",
      "gpu_count": 8,
      "precision": "bf16",
      "input_tokens": 1024,
      "output_tokens": 2048,
      "workload_type": "llm",
      "concurrencies": [1, 2, 4, 8]
    }
  ]
}
```

One scheduled sweep executes the named configuration once at each concurrency
level in `concurrencies`, and each of those produces one benchmark run. The
runner accepts the levels 1, 2, 4, 8, 16, 32, 64 and 128.

Assume every run you schedule completes successfully and records its metrics.

## Constraints

- **At most 23 sweeps.** GPU time is the budget; a plan that clears the floor
  with more sweeps than this is rejected. The floor can be cleared within 23.
- Only models and GPU types this platform has actually run. Do not invent
  hardware or models.
- Do not modify the corpus. Adding, deleting or editing rows in
  `benchmark_results` is not a plan, and the historical rows must survive
  unchanged.
- `/app/validate_plan.py` is not the acceptance check — read its header for
  what it does and does not cover.

## What you have to work out

The platform decides for itself what counts as a comparable peer, and what
makes a past run usable as one. That logic is already implemented and tested in
this repository — it is not described here, and you should not guess at it. Find
it, and apply exactly what it says. Two runs that look similar in a listing are
not necessarily peers, and a run that exists is not necessarily usable as one.

Everything you need is in the container: the service and worker source, the MCP
tool server and its tests, the API contract, `/app/docs`, and the database.

One disagreement inside the platform is worth knowing about, because it would
otherwise make this ambiguous. The REST listing endpoint drops any filter whose
value is unset or zero, so querying it can return rows that are not peers at
all. **Where the listing endpoint and the platform's peer-matching logic
disagree, the peer-matching logic is the definition.**

## Checking your work

```bash
python3 /app/validate_plan.py        # structure only; see its header
psql -d aistudio                     # the corpus
```

Your plan is graded by a check that is not in this container. It applies your
plan to the corpus and measures whether the floor is actually met.

Write a short `/app/plan_notes.md`: the rule you found and where, how you
counted, and why your plan fits the budget. One or two lines each.
