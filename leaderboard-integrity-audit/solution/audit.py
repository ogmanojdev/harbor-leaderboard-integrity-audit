"""
Oracle driver: reads the database, applies the validator, writes both artifacts.

Nothing here is hardcoded. The records are projected from the three tables, the
defect set comes from the validator, and the leaderboard is recomputed from the
surviving runs using the published aggregation rule.
"""

from __future__ import annotations

import json
import os
import sys

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.environ.get("VALIDATOR_DIR", "/app/app/services"))
from result_validator import _declared, validate_runs  # noqa: E402

OUT_DIR = os.environ.get("AUDIT_DIR", "/app/audit")


def build_records(cur) -> list[dict]:
    """Project workloads/tasks/task_logs/benchmark_results into run records."""
    cur.execute("""
        SELECT t.run_name AS run_id, t.task_config
        FROM tasks t ORDER BY t.run_name
    """)
    tasks = {r["run_id"]: dict(r) for r in cur.fetchall()}

    cur.execute("""
        SELECT t.run_name AS run_id, tl.line
        FROM tasks t JOIN task_logs tl ON tl.task_id = t.id
        ORDER BY t.run_name, tl.logged_at
    """)
    logs: dict[str, list[str]] = {}
    for row in cur.fetchall():
        logs.setdefault(row["run_id"], []).append(row["line"])

    cur.execute("""
        SELECT run_id, sub_run_index, concurrency, model_name, pipeline_version, gpu_type,
               gpu_count, precision, input_tokens, output_tokens, parallelism,
               status, total_token_throughput, mean_ttft_ms, node_ips,
               started_at, duration_seconds, metrics
        FROM benchmark_results ORDER BY run_id, sub_run_index
    """)
    rows: dict[str, list[dict]] = {}
    for row in cur.fetchall():
        d = dict(row)
        d["started_at"] = d["started_at"].isoformat()
        d["node_ips"] = list(d["node_ips"] or [])
        rows.setdefault(d["run_id"], []).append(d)

    return [
        {
            "run_id": run_id,
            "task_config": tasks.get(run_id, {}).get("task_config") or {},
            "log_lines": logs.get(run_id, []),
            "results": rows[run_id],
        }
        for run_id in sorted(rows)
    ]


def build_leaderboard(records: list[dict], defects: dict[str, list[str]]) -> list[dict]:
    """The published rule, applied to runs that survived the audit."""
    groups: dict[tuple, float] = {}

    for rec in records:
        if defects.get(rec["run_id"]):
            continue
        sweep = _declared(rec)["sweep"]
        if not sweep:
            continue
        target = max(sweep)
        peak = next(
            (r["total_token_throughput"] for r in rec["results"]
             if r["concurrency"] == target),
            None,
        )
        if peak is None:
            continue
        f = rec["results"][0]
        key = (f["model_name"], f["gpu_type"], f["precision"], f["parallelism"],
               f["gpu_count"], f["input_tokens"], f["output_tokens"])
        groups[key] = max(groups.get(key, 0.0), float(peak))

    entries = []
    for key, thr in groups.items():
        model, gpu_type, precision, parallelism, gpu_count, itok, otok = key
        entries.append({
            "model_name": model,
            "gpu_type": gpu_type,
            "precision": precision,
            "parallelism": parallelism,
            "gpu_count": gpu_count,
            "input_tokens": itok,
            "output_tokens": otok,
            "total_token_throughput": round(thr, 2),
            "per_gpu_throughput": round(thr / gpu_count, 2),
        })

    entries.sort(key=lambda e: (e["model_name"], -e["per_gpu_throughput"],
                                e["gpu_type"], e["precision"],
                                str(e["parallelism"])))
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["model_name"]] = counts.get(e["model_name"], 0) + 1
        e["rank_within_model"] = counts[e["model_name"]]
    return entries


def main() -> None:
    conn = psycopg2.connect(
        dbname=os.environ.get("PGDATABASE", "aistudio"),
        user=os.environ.get("PGUSER", "aistudio"),
        host=os.environ.get("PGHOST", "/var/run/postgresql"),
    )
    with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        records = build_records(cur)

    defects = validate_runs(records)
    os.makedirs(OUT_DIR, exist_ok=True)

    findings = [
        {
            "run_id": run_id,
            "defects": sorted(codes),
            "evidence": "recorded values disagree with tasks.task_config and/or "
                        "the launch arguments and declared sweep in task_logs",
        }
        for run_id, codes in sorted(defects.items())
    ]
    with open(f"{OUT_DIR}/findings.json", "w") as fh:
        json.dump({"findings": findings}, fh, indent=2, sort_keys=True)

    entries = build_leaderboard(records, defects)
    with open(f"{OUT_DIR}/leaderboard.json", "w") as fh:
        json.dump({"entries": entries}, fh, indent=2, sort_keys=True)

    print(f"records={len(records)} flagged={len(findings)} entries={len(entries)}")


if __name__ == "__main__":
    main()
