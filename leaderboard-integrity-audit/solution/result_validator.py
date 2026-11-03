"""
Reference implementation of the run integrity validator.

Decides, for each run record, which integrity defects it exhibits. Every
decision is made from evidence inside the record:

  * `task_config` is the snapshot of what was *requested*. It is authoritative
    when present, but it is empty for runs that predate the snapshot feature.
  * `log_lines` carry the launch arguments and the declared concurrency sweep,
    which is the only way to recover intent for those runs.
  * `results` are the rows ingest actually stored, defaults included.

A defect is a disagreement between what the run did and what was recorded, or a
structural problem with the recorded rows themselves.

Standard library only, no I/O: the function is pure so it can be exercised
against any corpus.
"""

from __future__ import annotations

import re

VALID_STATUSES = {"success", "failed"}

_TP = re.compile(r"--tensor-parallel-size\s+(\d+)")
_PP = re.compile(r"--pipeline-parallel-size\s+(\d+)")
_QUANT = re.compile(r"--quantization\s+([A-Za-z0-9_]+)")
_GPUS = re.compile(r"\bgpus=(\d+)")
_SWEEP = re.compile(r"concurrency sweep:\s*(.+?)\s*$")


def _declared(record: dict) -> dict:
    """What the run was *asked* to do: config snapshot first, logs as fallback."""
    cfg = record.get("task_config") or {}
    lines = record.get("log_lines") or []

    log_tp = log_pp = log_gpus = None
    log_quant = None
    sweep: list[int] = []
    for line in lines:
        if (m := _TP.search(line)):
            log_tp = int(m.group(1))
        if (m := _PP.search(line)):
            log_pp = int(m.group(1))
        if (m := _QUANT.search(line)):
            log_quant = m.group(1).lower()
        if (m := _GPUS.search(line)):
            log_gpus = int(m.group(1))
        if (m := _SWEEP.search(line)):
            sweep = [int(tok) for tok in m.group(1).split() if tok.isdigit()]

    if cfg.get("concurrency_sweep"):
        sweep = [int(c) for c in cfg["concurrency_sweep"]]

    return {
        "tp": cfg.get("tensor_parallel_size", log_tp),
        "pp": cfg.get("pipeline_parallel_size", log_pp),
        "precision": (cfg.get("precision") or log_quant or "").lower() or None,
        "gpu_count": cfg.get("gpu_count", log_gpus),
        "sweep": sweep,
    }


def _fingerprint(record: dict) -> str:
    """
    Identifies a logical measurement. Two runs sharing a fingerprint reported
    identical throughput at identical concurrency levels on the same node --
    which real re-measurement does not reproduce to the last decimal place.
    """
    rows = sorted(record.get("results") or [], key=lambda r: r.get("sub_run_index", 0))
    body = ";".join(
        f"{r.get('concurrency')}:{r.get('total_token_throughput')}" for r in rows
    )
    node = ",".join((record.get("results") or [{}])[0].get("node_ips") or [])
    return f"{node}|{body}"


def _earliest_start(record: dict) -> str:
    starts = [r.get("started_at") or "" for r in record.get("results") or []]
    return min(starts) if starts else ""


def validate_runs(records: list[dict]) -> dict[str, list[str]]:
    """Return {run_id: [defect_code, ...]} for every run exhibiting defects."""
    out: dict[str, list[str]] = {}

    # ── Per-run checks ────────────────────────────────────────────────────────
    for rec in records:
        run_id = rec.get("run_id")
        rows = rec.get("results") or []
        if not run_id or not rows:
            continue

        decl = _declared(rec)
        found: list[str] = []
        first = rows[0]

        # Parallelism omitted on a genuinely parallel run. A null parallelism on
        # a single-GPU run is not a defect: tp1 is the only possibility there,
        # so nothing about comparability is lost.
        multi_gpu = (decl["tp"] or 1) > 1 or (decl["pp"] or 1) > 1
        if multi_gpu and all(r.get("parallelism") is None for r in rows):
            found.append("missing_parallelism")

        # Recorded precision contradicts the precision actually used.
        rec_prec = (first.get("precision") or "").lower()
        if decl["precision"] and rec_prec and rec_prec != decl["precision"]:
            found.append("defaulted_precision")

        # Recorded GPU count contradicts the GPUs actually used.
        if decl["gpu_count"] and first.get("gpu_count") != decl["gpu_count"]:
            found.append("defaulted_gpu_count")

        # Throughput with no workload shape behind it.
        if not first.get("input_tokens") or not first.get("output_tokens"):
            found.append("zero_token_config")

        # Sweep recorded as successful but short of its declaration.
        if decl["sweep"]:
            present = {r.get("concurrency") for r in rows}
            if not set(decl["sweep"]).issubset(present):
                found.append("truncated_sweep")

        # Structural checks over the recorded rows.
        if any((r.get("status") or "").lower() not in VALID_STATUSES for r in rows):
            found.append("status_not_in_enum")

        if any((r.get("pipeline_version") or "") == "unknown" for r in rows):
            found.append("unknown_pipeline_version")

        durations = [r.get("duration_seconds") for r in rows if "duration_seconds" in r]
        if durations and any(d is None or d <= 0 for d in durations):
            found.append("clock_skew_duration")

        if found:
            out[run_id] = sorted(set(found))

    # ── Cross-run check: redundant re-executions ──────────────────────────────
    # Group by fingerprint; within a group every copy after the earliest start
    # is a redelivery rather than an independent measurement.
    by_fp: dict[str, list[dict]] = {}
    for rec in records:
        if rec.get("results"):
            by_fp.setdefault(_fingerprint(rec), []).append(rec)

    for group in by_fp.values():
        if len(group) < 2:
            continue
        for rec in sorted(group, key=_earliest_start)[1:]:
            rid = rec["run_id"]
            out.setdefault(rid, [])
            if "duplicate_logical_run" not in out[rid]:
                out[rid] = sorted(out[rid] + ["duplicate_logical_run"])

    return {k: v for k, v in out.items() if v}
