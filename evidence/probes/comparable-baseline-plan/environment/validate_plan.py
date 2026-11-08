#!/usr/bin/env python3
"""Structural check for /app/plan.json.

WHAT THIS CHECKS
  - the file exists and is valid JSON in the documented shape
  - every sweep names a model and a GPU type the platform has actually run
  - every concurrency level is one the sweep runner accepts
  - no sweep is missing a field, and no field has the wrong type

WHAT THIS DOES NOT CHECK
  - whether executing the plan actually leaves every reported configuration
    with enough eligible comparison peers
  - whether the plan is within the sweep budget
  - anything about peer eligibility

A plan can pass this script and still be wrong on all three counts. This is a
schema check, not an acceptance check.
"""
import json
import os
import sys

ALLOWED_CONCURRENCIES = [1, 2, 4, 8, 16, 32, 64, 128]
REQUIRED = {
    "model_name": str, "gpu_type": str, "gpu_count": int, "precision": str,
    "input_tokens": int, "output_tokens": int, "workload_type": str,
    "concurrencies": list,
}
PLAN = os.environ.get("PLAN_PATH", "/app/plan.json")


def known_entities():
    import subprocess
    def q(sql):
        r = subprocess.run(["psql", "-At", "-d", "aistudio", "-c", sql],
                           capture_output=True, text=True)
        return {x for x in r.stdout.split() if x}
    return q("select distinct model_name from benchmark_results"), \
           q("select distinct gpu_type from benchmark_results")


def main():
    errs = []
    if not os.path.exists(PLAN):
        print(f"FAIL: {PLAN} does not exist")
        return 1
    try:
        plan = json.load(open(PLAN))
    except Exception as e:
        print(f"FAIL: {PLAN} is not valid JSON: {e}")
        return 1

    sweeps = plan.get("sweeps") if isinstance(plan, dict) else None
    if not isinstance(sweeps, list):
        print('FAIL: the plan must be an object with a "sweeps" list')
        return 1

    models, gpus = known_entities()
    for i, s in enumerate(sweeps):
        if not isinstance(s, dict):
            errs.append(f"sweep {i}: not an object")
            continue
        for k, t in REQUIRED.items():
            if k not in s:
                errs.append(f"sweep {i}: missing {k}")
            elif not isinstance(s[k], t) or isinstance(s[k], bool):
                errs.append(f"sweep {i}: {k} should be {t.__name__}")
        if isinstance(s.get("concurrencies"), list):
            if not s["concurrencies"]:
                errs.append(f"sweep {i}: concurrencies is empty")
            for c in s["concurrencies"]:
                if c not in ALLOWED_CONCURRENCIES:
                    errs.append(f"sweep {i}: concurrency {c!r} is not a level the runner accepts")
        if s.get("model_name") and s["model_name"] not in models:
            errs.append(f"sweep {i}: model_name {s['model_name']!r} has never run on this platform")
        if s.get("gpu_type") and s["gpu_type"] not in gpus:
            errs.append(f"sweep {i}: gpu_type {s['gpu_type']!r} has never run on this platform")

    if errs:
        print(f"FAIL: {len(errs)} structural problem(s)")
        for e in errs[:40]:
            print("  -", e)
        return 1

    print(f"PASS: {len(sweeps)} sweep(s) are structurally valid.")
    print("Reminder: this script does not check peer coverage, peer eligibility,")
    print("or the sweep budget. A structurally valid plan can still be rejected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
