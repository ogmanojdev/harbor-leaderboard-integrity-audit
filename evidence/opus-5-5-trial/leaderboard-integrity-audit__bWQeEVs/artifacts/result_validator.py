"""Integrity validation for stored benchmark runs.

The ingest endpoint (``app/routers/ingest.py``) fills in defaults for config
fields a runner omits (``precision="fp16"``, ``gpu_count=1``,
``input_tokens=0``, ``output_tokens=0``, ``pipeline_version="unknown"``,
``parallelism=None``, ``duration_seconds=None``).  A defaulted value looks
exactly like a real one afterwards, so this module re-derives what each run
*actually* did from independent evidence and compares it with what was stored:

* ``task_config``  -- the config snapshot taken when the task was launched
  (may be ``{}`` for tasks that predate snapshots);
* ``log_lines``    -- the captured SSH output (``[bench] ...`` header lines,
  the ``vllm serve`` launch line, ``BENCH_RESULT:{...}`` lines); the header
  may be missing when the log stream dropped and reconnected;
* ``results[*].metrics`` -- the raw runner payload, which sometimes carries
  ``server_args``, ``actual_dtype``, ``parallelism``, ``visible_devices`` or
  ``request_params``.

Pure standard library, no I/O, no side effects.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Iterable, Optional

DEFECT_CODES = (
    "missing_parallelism",
    "defaulted_precision",
    "defaulted_gpu_count",
    "zero_token_config",
    "duplicate_logical_run",
    "truncated_sweep",
    "clock_skew_duration",
    "status_not_in_enum",
    "unknown_pipeline_version",
)

VALID_STATUSES = {"success", "failed"}

_SWEEP_RE = re.compile(r"concurrency\s+sweep\s*[:=]\s*(.*)$", re.I)
_GPUS_RE = re.compile(r"\bgpus\s*=\s*(\d+)", re.I)
_BENCH_RE = re.compile(r"BENCH_RESULT\s*:\s*(\{.*\})")


# ── small helpers ──────────────────────────────────────────────────────────

def _int(v: Any) -> Optional[int]:
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip().lower()
    return s or None


def _parse_dt(v: Any) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str) and v.strip():
        s = v.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def _flag(args: str, *names: str) -> Optional[str]:
    """Return the value of a CLI flag (``--x v`` or ``--x=v``) in ``args``."""
    for name in names:
        m = re.search(r"(?:^|\s)" + re.escape(name) + r"(?:=|\s+)(\S+)", args)
        if m:
            return m.group(1)
    return None


def _parse_server_cmd(cmd: str) -> dict:
    """Extract tp / pp / precision from a ``vllm serve ...`` command line."""
    out: dict = {}
    tp = _int(_flag(cmd, "--tensor-parallel-size", "-tp"))
    pp = _int(_flag(cmd, "--pipeline-parallel-size", "-pp"))
    if tp is not None:
        out["tp"] = tp
    if pp is not None:
        out["pp"] = pp
    quant = _norm(_flag(cmd, "--quantization", "-q"))
    dtype = _norm(_flag(cmd, "--dtype"))
    if quant and quant not in ("none", "auto"):
        out["precision"] = quant
    elif dtype and dtype != "auto":
        out["precision"] = dtype
    mml = _int(_flag(cmd, "--max-model-len"))
    if mml is not None:
        out["max_model_len"] = mml
    return out


def _parallelism_str(tp: int, pp: int) -> str:
    """Same encoding as the ingest endpoint."""
    if tp > 1 and pp > 1:
        return f"tp{tp}pp{pp}"
    if pp > 1:
        return f"pp{pp}"
    if tp > 1:
        return f"tp{tp}"
    return "tp1"


def _first(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


# ── evidence extraction ────────────────────────────────────────────────────

def _log_evidence(lines: Iterable[Any]) -> dict:
    ev: dict = {"bench": []}
    for raw in lines or []:
        if not isinstance(raw, str):
            continue
        line = raw.strip()
        m = _BENCH_RE.search(line)
        if m:
            try:
                obj = json.loads(m.group(1))
                if isinstance(obj, dict):
                    ev["bench"].append(obj)
            except ValueError:
                pass
            continue
        m = _SWEEP_RE.search(line)
        if m and "sweep" not in ev:
            vals = [_int(x) for x in re.split(r"[\s,\[\]]+", m.group(1)) if x]
            vals = [v for v in vals if v is not None]
            if vals:
                ev["sweep"] = vals
            continue
        if "vllm serve" in line or "launching" in line.lower():
            idx = line.find("vllm serve")
            cmd = line[idx:] if idx >= 0 else line
            parsed = _parse_server_cmd(cmd)
            if parsed and "launch" not in ev:
                ev["launch"] = parsed
            continue
        m = _GPUS_RE.search(line)
        if m and "node_gpus" not in ev:
            ev["node_gpus"] = int(m.group(1))
    return ev


def _metrics_evidence(results: list) -> dict:
    ev: dict = {}
    for r in results:
        m = r.get("metrics") or {}
        if not isinstance(m, dict):
            continue
        if "actual_dtype" not in ev and _norm(m.get("actual_dtype")):
            ev["actual_dtype"] = _norm(m.get("actual_dtype"))
        if "server" not in ev and isinstance(m.get("server_args"), str):
            ev["server"] = _parse_server_cmd(m["server_args"])
            ev["server_has_pp_flag"] = "pipeline-parallel" in m["server_args"] or " -pp" in m["server_args"]
            ev["server_has_tp_flag"] = "tensor-parallel" in m["server_args"] or " -tp" in m["server_args"]
        p = m.get("parallelism")
        if "par" not in ev and isinstance(p, dict):
            tp = _int(p.get("tensor_parallel_size"))
            pp = _int(p.get("pipeline_parallel_size"))
            if tp is not None or pp is not None:
                ev["par"] = (tp or 1, pp or 1)
        vd = m.get("visible_devices")
        if "visible" not in ev:
            if isinstance(vd, list) and vd:
                ev["visible"] = len(vd)
            elif isinstance(vd, str) and vd.strip():
                ev["visible"] = len([x for x in vd.split(",") if x.strip()])
        rp = m.get("request_params")
        if "req" not in ev and isinstance(rp, dict):
            ev["req"] = rp
    return ev


def _truth(record: dict) -> dict:
    """Best estimate of what the run actually used, from independent sources."""
    cfg = record.get("task_config") or {}
    if not isinstance(cfg, dict):
        cfg = {}
    results = [r for r in (record.get("results") or []) if isinstance(r, dict)]
    log = _log_evidence(record.get("log_lines") or [])
    met = _metrics_evidence(results)
    launch = log.get("launch", {})
    server = met.get("server", {})

    # tensor / pipeline parallel sizes
    tp = pp = None
    if _int(cfg.get("tensor_parallel_size")) is not None or _int(cfg.get("pipeline_parallel_size")) is not None:
        tp = _int(cfg.get("tensor_parallel_size")) or 1
        pp = _int(cfg.get("pipeline_parallel_size")) or 1
    elif "tp" in launch or "pp" in launch:
        tp, pp = launch.get("tp", 1), launch.get("pp", 1)
    elif "par" in met:
        tp, pp = met["par"]
    elif "tp" in server or "pp" in server:
        tp, pp = server.get("tp", 1), server.get("pp", 1)

    # precision
    precision = _first(
        _norm(cfg.get("precision")),
        launch.get("precision"),
        met.get("actual_dtype"),
        server.get("precision"),
    )

    # GPU count
    gpu_count = _int(cfg.get("gpu_count"))
    if gpu_count is None and tp is not None:
        gpu_count = tp * pp
    if gpu_count is None:
        gpu_count = met.get("visible")

    # workload shape
    req = met.get("req") or {}
    input_tokens = _first(_int(cfg.get("input_tokens")), _int(req.get("random_input_len")),
                          _int(req.get("input_len")), _int(req.get("input_tokens")))
    output_tokens = _first(_int(cfg.get("output_tokens")), _int(req.get("random_output_len")),
                           _int(req.get("output_len")), _int(req.get("output_tokens")))

    # declared sweep
    sweep = None
    cs = cfg.get("concurrency_sweep")
    if isinstance(cs, (list, tuple)) and cs:
        sweep = [v for v in (_int(x) for x in cs) if v is not None]
    elif isinstance(cs, str) and cs.strip():
        sweep = [v for v in (_int(x) for x in re.split(r"[\s,]+", cs)) if v is not None]
    if not sweep:
        sweep = log.get("sweep")

    return {
        "tp": tp,
        "pp": pp,
        "precision": precision,
        "gpu_count": gpu_count,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "sweep": sweep or None,
        "pipeline_version": _norm(cfg.get("pipeline_version")),
        "bench": log.get("bench", []),
    }


def declared_sweep(record: dict) -> Optional[list]:
    """The concurrency sweep the run declared (config snapshot, else logs)."""
    return _truth(record)["sweep"]


def recorded_concurrencies(record: dict) -> set:
    out = set()
    for r in record.get("results") or []:
        if not isinstance(r, dict):
            continue
        c = _int(r.get("concurrency"))
        if c is not None and _num(r.get("total_token_throughput")) is not None:
            out.add(c)
    return out


# ── per-run checks ─────────────────────────────────────────────────────────

def _check_run(record: dict) -> list:
    results = [r for r in (record.get("results") or []) if isinstance(r, dict)]
    if not results:
        return []
    t = _truth(record)
    defects: list = []

    # missing_parallelism
    rec_par = [_norm(r.get("parallelism")) for r in results]
    if any(p is None for p in rec_par):
        multi = False
        if t["tp"] is not None:
            multi = (t["tp"] * t["pp"]) > 1
        elif t["gpu_count"] is not None:
            multi = t["gpu_count"] > 1
        if multi:
            defects.append("missing_parallelism")

    # defaulted_precision
    if t["precision"] is not None:
        if any(_norm(r.get("precision")) != t["precision"] for r in results):
            defects.append("defaulted_precision")

    # defaulted_gpu_count
    if t["gpu_count"] is not None:
        if any(_int(r.get("gpu_count")) != t["gpu_count"] for r in results):
            defects.append("defaulted_gpu_count")

    # zero_token_config
    for r in results:
        it, ot = _int(r.get("input_tokens")), _int(r.get("output_tokens"))
        if (it is not None and it <= 0) or (ot is not None and ot <= 0):
            defects.append("zero_token_config")
            break

    # truncated_sweep: declared sweep not fully recorded, yet not recorded as failed
    statuses = [_norm(r.get("status")) for r in results]
    recorded_failed = any(s == "failed" for s in statuses)
    if t["sweep"] and not recorded_failed:
        if not set(t["sweep"]).issubset(recorded_concurrencies(record)):
            defects.append("truncated_sweep")

    # clock_skew_duration
    for r in results:
        if "duration_seconds" in r:
            d = _num(r.get("duration_seconds"))
            if d is None or d <= 0:
                defects.append("clock_skew_duration")
                break
            continue
        s, c = _parse_dt(r.get("started_at")), _parse_dt(r.get("completed_at"))
        if s is not None and c is not None:
            try:
                if (c - s).total_seconds() <= 0:
                    defects.append("clock_skew_duration")
                    break
            except TypeError:  # naive vs aware
                pass

    # status_not_in_enum (stored value must be exactly one of the enum)
    if any(r.get("status") not in VALID_STATUSES for r in results):
        defects.append("status_not_in_enum")

    # unknown_pipeline_version
    for r in results:
        pv = _norm(r.get("pipeline_version"))
        if pv is None or pv == "unknown":
            defects.append("unknown_pipeline_version")
            break

    return defects


# ── cross-run check: duplicate logical runs ────────────────────────────────

def _fingerprint(record: dict):
    """Exact measurement fingerprint; independent runs never reproduce every
    throughput figure to the last digit."""
    pts = []
    for r in record.get("results") or []:
        if not isinstance(r, dict):
            continue
        c, thr = _int(r.get("concurrency")), _num(r.get("total_token_throughput"))
        if c is None or thr is None:
            continue
        pts.append((c, thr, _num(r.get("mean_ttft_ms"))))
    if not pts:
        return None
    first = next(r for r in record["results"] if isinstance(r, dict))
    return (
        _norm(first.get("model_name")),
        _norm(first.get("gpu_type")),
        tuple(sorted(pts)),
    )


def _run_start(record: dict):
    starts = [_parse_dt(r.get("started_at")) for r in record.get("results") or [] if isinstance(r, dict)]
    starts = [s for s in starts if s is not None]
    if not starts:
        return None
    try:
        return min(starts)
    except TypeError:
        return starts[0]


def _duplicates(records: list) -> set:
    groups: dict = {}
    for rec in records:
        fp = _fingerprint(rec)
        if fp is not None:
            groups.setdefault(fp, []).append(rec)
    dups = set()
    for recs in groups.values():
        if len(recs) < 2:
            continue

        def key(r):
            s = _run_start(r)
            ts = s.timestamp() if s is not None and s.tzinfo is not None else float("inf")
            return (ts, str(r.get("run_id")))

        recs = sorted(recs, key=key)
        for r in recs[1:]:
            if r.get("run_id") != recs[0].get("run_id"):
                dups.add(r.get("run_id"))
    return dups


# ── public API ─────────────────────────────────────────────────────────────

def validate_runs(records: list[dict]) -> dict[str, list[str]]:
    """Return {run_id: [defect_code, ...]} for every run with defects.

    Runs with no defects may be omitted, or mapped to an empty list.
    Defect codes must come from the published vocabulary.
    """
    out: dict = {}
    records = [r for r in (records or []) if isinstance(r, dict) and r.get("run_id") is not None]
    for rec in records:
        try:
            d = _check_run(rec)
        except Exception:  # never let one malformed record break the audit
            d = []
        if d:
            out.setdefault(rec["run_id"], [])
            for code in d:
                if code not in out[rec["run_id"]]:
                    out[rec["run_id"]].append(code)
    try:
        dups = _duplicates(records)
    except Exception:
        dups = set()
    for rid in dups:
        out.setdefault(rid, [])
        if "duplicate_logical_run" not in out[rid]:
            out[rid].append("duplicate_logical_run")
    return {k: [c for c in DEFECT_CODES if c in v] for k, v in out.items() if v}
