#!/usr/bin/env python3
"""
Deterministic generator for benchmark-run fixtures.

Produces (a) SQL INSERTs for a populated `benchmark_results` / `task_logs`
database and (b) a ground-truth JSON manifest naming every defect it injected.

The same generator produces both the seed corpus the agent inspects and the
held-out corpus the verifier scores the agent's validator against; only the RNG
seed and run count differ. That is what makes "does the validator generalise?"
answerable: the held-out corpus is same-distribution but shares no run_id.

Defect taxonomy is grounded in the real defaulting behaviour of
`app/routers/ingest.py` in corespan/aistudio-server -- see DESIGN_JOURNAL.md.
Nothing here is an invented trick: each defect is what that code records when a
runner omits a field.

Usage:
    gen_runs.py --seed 20261102 --runs 48 --out-sql seed.sql --out-truth truth.json
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone

# ── Defect codes ──────────────────────────────────────────────────────────────
# These are the exact strings the agent must use in findings.json. They are
# published in instruction.md, so grading on them is not brittle string matching
# -- it is a documented enum.

MISSING_PARALLELISM = "missing_parallelism"
DEFAULTED_PRECISION = "defaulted_precision"
DEFAULTED_GPU_COUNT = "defaulted_gpu_count"
ZERO_TOKEN_CONFIG = "zero_token_config"
DUPLICATE_LOGICAL_RUN = "duplicate_logical_run"
TRUNCATED_SWEEP = "truncated_sweep"

ALL_DEFECTS = [
    MISSING_PARALLELISM,
    DEFAULTED_PRECISION,
    DEFAULTED_GPU_COUNT,
    ZERO_TOKEN_CONFIG,
    DUPLICATE_LOGICAL_RUN,
    TRUNCATED_SWEEP,
]

# ── Recipe catalogue ──────────────────────────────────────────────────────────
# Mirrors the real benchmark scripts in benchmarks/{h100,mi210,rtx5090,t4}/ so
# the declared concurrency sweeps and parallelism strategies match files the
# agent can actually read.

SWEEP = [1, 2, 4, 8, 16, 32, 64, 128]


@dataclass(frozen=True)
class Recipe:
    name: str
    model: str
    gpu_type: str
    gpu_model: str
    gpu_count: int
    tp: int
    pp: int
    precision: str
    input_tokens: int
    output_tokens: int
    server_name: str
    pipeline_version: str
    # Per-GPU tokens/sec at saturation. Rough but plausible shape; the absolute
    # values do not matter, only that comparisons between runs are meaningful.
    peak_per_gpu: float

    @property
    def parallelism(self) -> str:
        if self.tp > 1 and self.pp > 1:
            return f"tp{self.tp}pp{self.pp}"
        if self.pp > 1:
            return f"pp{self.pp}"
        if self.tp > 1:
            return f"tp{self.tp}"
        return "tp1"


RECIPES = [
    Recipe("h100/llama31-70b-c128", "llama31-70b", "h100", "NVIDIA H100 80GB HBM3",
           2, 2, 1, "bf16", 1024, 1024, "PRU", "vllm-openai:v0.14.1", 1180.0),
    Recipe("h100/llama31-70b-c256", "llama31-70b", "h100", "NVIDIA H100 80GB HBM3",
           2, 2, 1, "fp8", 2048, 512, "PRU", "vllm-openai:v0.14.1", 1910.0),
    Recipe("mi210/llama31-70b-tp4", "llama31-70b", "mi210", "AMD Instinct MI210",
           4, 4, 1, "bf16", 1024, 1024, "SuperMicro", "vllm-openai:v0.14.1", 410.0),
    Recipe("mi210/llama31-70b-tp8", "llama31-70b", "mi210", "AMD Instinct MI210",
           8, 8, 1, "bf16", 1024, 1024, "SuperMicro", "vllm-openai:v0.14.1", 372.0),
    Recipe("mi210/llama33-70b-tp8", "llama33-70b", "mi210", "AMD Instinct MI210",
           8, 8, 1, "bf16", 1024, 1024, "SuperMicro", "vllm-openai:v0.14.1", 364.0),
    Recipe("mi210/deepseek-r1-70b-tp8", "deepseek-r1-70b", "mi210", "AMD Instinct MI210",
           8, 8, 1, "bf16", 1024, 2048, "SuperMicro", "vllm-openai:v0.14.1", 331.0),
    Recipe("rtx5090/qwen25-32b-tp4-bf16", "qwen25-32b", "rtx5090", "NVIDIA GeForce RTX 5090",
           4, 4, 1, "bf16", 1024, 1024, "PRU", "vllm-openai:v0.14.1", 690.0),
    Recipe("rtx5090/qwen25-32b-pp4-fp8", "qwen25-32b", "rtx5090", "NVIDIA GeForce RTX 5090",
           4, 1, 4, "fp8", 1024, 1024, "PRU", "vllm-openai:v0.14.1", 1120.0),
    Recipe("t4/tinyllama-tp1", "tinyllama-1.1b", "t4", "Tesla T4",
           1, 1, 1, "fp16", 512, 512, "Dell Inc.", "vllm-openai:v0.14.1", 2400.0),
    Recipe("t4/tinyllama-tp2", "tinyllama-1.1b", "t4", "Tesla T4",
           2, 2, 1, "fp16", 512, 512, "Dell Inc.", "vllm-openai:v0.14.1", 2050.0),
]


def saturation(concurrency: int) -> float:
    """Throughput rises with concurrency and saturates. Monotone, deterministic."""
    return concurrency / (concurrency + 6.0) * 1.45


@dataclass
class SubRun:
    sub_run_index: int
    concurrency: int
    total_token_throughput: float
    mean_ttft_ms: float
    mean_tpot_ms: float
    mean_e2el_ms: float


@dataclass
class Run:
    run_id: str
    recipe: Recipe
    started_at: datetime
    node_ips: list[str]
    sub_runs: list[SubRun]
    # Values as *recorded* by ingest, which may differ from the recipe when a
    # defect is applied.
    rec_precision: str = ""
    rec_gpu_count: int = 0
    rec_parallelism: str | None = None
    rec_input_tokens: int = 0
    rec_output_tokens: int = 0
    rec_pipeline_version: str = ""
    defects: list[str] = field(default_factory=list)
    # Corroborating evidence that survives in the metrics JSONB blob, which the
    # real ingest path stores verbatim. This is what makes each defect
    # *discoverable* rather than a guess.
    blob_extra: dict = field(default_factory=dict)
    declared_sweep: list[int] = field(default_factory=lambda: list(SWEEP))
    # Older tasks predate the task_config snapshot feature and carry an empty
    # config. Those runs can only be reconstructed from the task logs, so a
    # pure SQL diff of requested-vs-recorded will not find them.
    snapshot_missing: bool = False
    # Runs whose SSE log capture dropped: the early lines were never written to
    # task_logs, so their intent survives only in the config snapshot. Evidence
    # is deliberately complementary -- neither source alone covers the corpus.
    log_gap: bool = False


def build_run(rng: random.Random, recipe: Recipe, idx: int, day: datetime) -> Run:
    # Per-corpus unique id drawn from the seeded stream, so the seed and
    # held-out corpora share no run_id. That disjointness is what makes
    # "does the agent's validator generalise?" a real question.
    uid = f"{rng.getrandbits(24):06x}"
    run_id = f"{recipe.gpu_type}-{recipe.model}-{day:%Y%m%d}-{uid}"
    jitter = 1.0 + rng.uniform(-0.03, 0.03)
    sub_runs = []
    for i, c in enumerate(SWEEP):
        per_gpu = recipe.peak_per_gpu * saturation(c) * jitter
        total = per_gpu * recipe.gpu_count
        ttft = 42.0 + c * (3.1 if recipe.gpu_type in ("h100", "rtx5090") else 5.4)
        tpot = 1000.0 / max(per_gpu / 8.0, 1.0)
        sub_runs.append(SubRun(
            sub_run_index=i,
            concurrency=c,
            total_token_throughput=round(total, 2),
            mean_ttft_ms=round(ttft * jitter, 2),
            mean_tpot_ms=round(tpot * jitter, 3),
            mean_e2el_ms=round((ttft + tpot * recipe.output_tokens) * jitter, 2),
        ))
    octet = rng.randint(10, 240)
    return Run(
        run_id=run_id,
        recipe=recipe,
        started_at=day,
        node_ips=[f"10.6.12.{octet}"],
        sub_runs=sub_runs,
        rec_precision=recipe.precision,
        rec_gpu_count=recipe.gpu_count,
        rec_parallelism=recipe.parallelism,
        rec_input_tokens=recipe.input_tokens,
        rec_output_tokens=recipe.output_tokens,
        rec_pipeline_version=recipe.pipeline_version,
    )


# ── Defect injectors ──────────────────────────────────────────────────────────
# Each injector mutates what ingest *recorded* and leaves corroborating evidence
# in the metrics blob or task logs. The evidence is the fair part: every defect
# is provable from data the agent can read.

def inject_missing_parallelism(run: Run) -> None:
    """Runner omitted metrics.parallelism -> ingest leaves the column NULL."""
    run.rec_parallelism = None
    run.blob_extra["server_args"] = (
        f"vllm serve {run.recipe.model} --tensor-parallel-size {run.recipe.tp} "
        f"--pipeline-parallel-size {run.recipe.pp} --dtype {run.recipe.precision}"
    )
    run.defects.append(MISSING_PARALLELISM)


def inject_defaulted_precision(run: Run) -> None:
    """Runner omitted config.precision -> ingest silently records 'fp16'."""
    if run.recipe.precision == "fp16":
        return  # nothing to hide; would be indistinguishable from a valid run
    run.rec_precision = "fp16"
    run.blob_extra["server_args"] = (
        f"vllm serve {run.recipe.model} --tensor-parallel-size {run.recipe.tp} "
        f"--quantization {run.recipe.precision} --dtype auto"
    )
    run.blob_extra["actual_dtype"] = run.recipe.precision
    run.defects.append(DEFAULTED_PRECISION)


def inject_defaulted_gpu_count(run: Run) -> None:
    """Runner omitted config.gpu_count -> ingest silently records 1."""
    if run.recipe.gpu_count == 1:
        return
    run.rec_gpu_count = 1
    run.blob_extra["parallelism"] = {
        "tensor_parallel_size": run.recipe.tp,
        "pipeline_parallel_size": run.recipe.pp,
    }
    run.blob_extra["visible_devices"] = list(range(run.recipe.gpu_count))
    run.defects.append(DEFAULTED_GPU_COUNT)


def inject_zero_token_config(run: Run) -> None:
    """Runner omitted input/output token config -> ingest records 0."""
    run.rec_input_tokens = 0
    run.rec_output_tokens = 0
    run.blob_extra["request_params"] = {
        "random_input_len": run.recipe.input_tokens,
        "random_output_len": run.recipe.output_tokens,
    }
    run.defects.append(ZERO_TOKEN_CONFIG)


def inject_truncated_sweep(run: Run, rng: random.Random) -> None:
    """
    Worker died mid-sweep but the row was still marked success. The declared
    sweep survives in the task logs, so the gap is provable.
    """
    keep = rng.choice([3, 4, 5])
    run.sub_runs = run.sub_runs[:keep]
    run.defects.append(TRUNCATED_SWEEP)


def make_duplicate(run: Run, rng: random.Random) -> Run:
    """
    Same logical run re-POSTed under a fresh run_id. The UniqueConstraint on
    (run_id, sub_run_index) cannot catch this, so both copies persist.
    Provable by fingerprint: identical started_at, node_ips and metrics.
    """
    import copy
    dup = copy.deepcopy(run)
    # A redelivered task gets a fresh run_name, not a recognisable suffix.
    head = run.run_id.rsplit("-", 1)[0]
    dup.run_id = f"{head}-{rng.getrandbits(24):06x}"
    # The redelivery fires later, which is what makes "the redundant copy"
    # well defined: same measured metrics, later start. Identical throughput
    # to 2dp across every sub-run is the tell -- real re-measurement never
    # reproduces exactly.
    dup.started_at = run.started_at + timedelta(minutes=37)
    dup.defects = [DUPLICATE_LOGICAL_RUN]
    dup.blob_extra = dict(run.blob_extra)
    return dup


# ── Decoys ────────────────────────────────────────────────────────────────────
# Runs that trip a naive heuristic but are genuinely valid. These exist to
# measure false positives: a validator that flags "gpu_count == 1" or
# "len(sub_runs) < 8" as defective will reject these and lose points.
#
# Nothing in the corpus marks them. An earlier version tagged each decoy in its
# metrics blob, which told a reader those runs were safe and quietly disarmed
# the very test they exist to run. The notes below stay in the ground-truth
# manifest, which only the verifier sees.

DECOY_NOTES = {
    "genuine_single_gpu": "gpu_count=1 and parallelism=tp1 are correct for a t4 single-GPU recipe.",
    "genuine_fp8": "precision=fp8 is correctly recorded, not defaulted.",
    "genuine_short_sweep": "recipe declares a 4-point sweep, so 4 sub-runs is complete.",
}


def build_corpus(seed: int, n_runs: int) -> tuple[list[Run], dict]:
    rng = random.Random(seed)
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    runs: list[Run] = []

    for i in range(n_runs):
        recipe = RECIPES[rng.randrange(len(RECIPES))]
        day = base + timedelta(days=rng.randrange(0, 55), hours=rng.randrange(0, 20))
        runs.append(build_run(rng, recipe, i, day))

    # Decoy 1: a genuinely short sweep. The declared sweep is short too, so a
    # validator must compare against the declaration, not against len(SWEEP).
    short = build_run(rng, RECIPES[8], 900, base + timedelta(days=60))
    short.declared_sweep = [1, 2, 4, 8]
    short.sub_runs = short.sub_runs[:4]
    runs.append(short)

    # Decoy 2: correctly-recorded fp8. Must not be read as a defaulted precision.
    fp8 = build_run(rng, RECIPES[7], 901, base + timedelta(days=61))
    fp8.blob_extra["server_args"] = (
        f"vllm serve {fp8.recipe.model} --pipeline-parallel-size 4 --quantization fp8"
    )
    runs.append(fp8)

    # Decoy 3: a real single-GPU run.
    single = build_run(rng, RECIPES[8], 902, base + timedelta(days=62))
    runs.append(single)

    # Apply defects to a deterministic, disjoint selection of the corpus.
    # Some defects are only meaningful on some recipes: defaulting precision to
    # fp16 is invisible on a recipe that genuinely is fp16, and defaulting
    # gpu_count to 1 is invisible on a single-GPU recipe. Selection is therefore
    # filtered rather than uniform, so every defect class is actually populated.
    order = list(range(n_runs))
    rng.shuffle(order)
    used: set[int] = set()

    def take(k: int, pred=None) -> list[int]:
        picked: list[int] = []
        for i in order:
            if len(picked) == k:
                break
            if i in used or (pred is not None and not pred(runs[i])):
                continue
            used.add(i)
            picked.append(i)
        if len(picked) < k:
            raise RuntimeError(f"corpus too small to place {k} defects")
        return picked

    # Only inject onto multi-GPU recipes: a NULL parallelism on a genuinely
    # single-GPU run has no comparability consequence, so flagging it would
    # punish a correct validator for sensible restraint.
    for i in take(3, lambda r: r.recipe.tp > 1 or r.recipe.pp > 1):
        inject_missing_parallelism(runs[i])
    for i in take(3, lambda r: r.recipe.precision != "fp16"):
        inject_defaulted_precision(runs[i])
    for i in take(3, lambda r: r.recipe.gpu_count > 1):
        inject_defaulted_gpu_count(runs[i])
    for i in take(2):
        inject_zero_token_config(runs[i])
    for i in take(3):
        inject_truncated_sweep(runs[i], rng)

    dups = [make_duplicate(runs[i], rng) for i in take(2)]
    runs.extend(dups)

    # ~30% of tasks carry no config snapshot. At least two defective runs are
    # included so that a config-diff-only strategy provably misses something.
    defective = [r for r in runs if r.defects]
    clean = [r for r in runs if not r.defects]
    rng.shuffle(defective)
    rng.shuffle(clean)
    for r in defective[:2]:
        r.snapshot_missing = True
    n_more = max(0, int(0.3 * len(runs)) - 2)
    for r in clean[:n_more]:
        r.snapshot_missing = True

    # A run never loses both sources: that would make it unprovable. Runs with a
    # config snapshot may lose their early log lines; runs without one keep them.
    gap_pool = [r for r in runs if not r.snapshot_missing]
    rng.shuffle(gap_pool)
    for r in [r for r in gap_pool if r.defects][:3]:
        r.log_gap = True
    still = [r for r in gap_pool if not r.log_gap]
    for r in still[:max(0, int(0.22 * len(runs)) - 3)]:
        r.log_gap = True

    truth = {
        "generator_seed": seed,
        "defect_codes": ALL_DEFECTS,
        "decoy_notes": DECOY_NOTES,
        "runs": {
            r.run_id: {
                "defects": sorted(set(r.defects)),
                "recipe": r.recipe.name,
                "declared_sweep": r.declared_sweep,
                "valid": not r.defects,
            }
            for r in runs
        },
    }
    return runs, truth


def log_lines_for(run: Run, machine_hid: str = "node-000000") -> list[str]:
    """
    The log stream as `task_logs` captured it.

    A run whose capture dropped has no recipe, node, declared sweep or launch
    line -- only the reconnect marker and whatever arrived afterwards. The
    marker is left in deliberately: an agent must be able to tell that the
    stream is incomplete rather than conclude the run never launched.

    Nothing marks a truncated sweep. A worker killed mid-run writes no farewell,
    so an incomplete sweep is only visible by counting what arrived against what
    was declared.
    """
    lines: list[str] = []
    if run.log_gap:
        lines.append("[sse] log stream reconnected after transport error; "
                     "earlier output for this task was not captured")
    else:
        lines.extend([
            f"[bench] recipe={run.recipe.name}",
            f"[bench] node={machine_hid} ip={run.node_ips[0]} "
            f"gpus={run.recipe.gpu_count} ({run.recipe.gpu_model})",
            f"[bench] concurrency sweep: "
            f"{' '.join(str(c) for c in run.declared_sweep)}",
            f"[bench] launching: vllm serve {run.recipe.model} "
            f"--tensor-parallel-size {run.recipe.tp} "
            f"--pipeline-parallel-size {run.recipe.pp} "
            f"--quantization {run.recipe.precision} "
            f"--max-model-len {run.recipe.input_tokens + run.recipe.output_tokens}",
        ])
    for sub in run.sub_runs:
        lines.append("BENCH_RESULT:" + json.dumps(
            {"concurrency": sub.concurrency,
             "total_token_throughput": sub.total_token_throughput},
            sort_keys=True))
    return lines


# ── Expected corrected leaderboard ────────────────────────────────────────────
# The aggregation rule is published verbatim in instruction.md so the expected
# output is fully determined. Grading compares numbers, not prose.
#
#   1. Consider only runs with no integrity defects.
#   2. A run's peak is its total_token_throughput at the highest concurrency in
#      its recipe's declared sweep. A run missing that point has no peak and is
#      excluded.
#   3. Group by (model_name, gpu_type, precision, parallelism, gpu_count,
#      input_tokens, output_tokens).
#   4. A group's throughput is the max peak among its runs.
#   5. per_gpu_throughput = throughput / gpu_count, rounded to 2 dp.
#   6. Within each model_name, rank by per_gpu_throughput descending; ties are
#      broken by (gpu_type, precision, parallelism) ascending.

def expected_leaderboard(runs: list[Run]) -> list[dict]:
    groups: dict[tuple, list] = {}
    for r in runs:
        if r.defects:
            continue
        # A run is eligible only if it recorded a result at every concurrency it
        # declared. An incomplete sweep is not a slower run, it is an unfinished
        # measurement, and averaging it in would understate the configuration.
        present = {s.concurrency for s in r.sub_runs}
        if not set(r.declared_sweep).issubset(present):
            continue
        peak = max(s.total_token_throughput for s in r.sub_runs)
        key = (
            r.recipe.model, r.recipe.gpu_type, r.rec_precision,
            r.rec_parallelism, r.rec_gpu_count,
            r.rec_input_tokens, r.rec_output_tokens,
        )
        if key in groups:
            groups[key][0] = max(groups[key][0], peak)
            groups[key][1] += 1
        else:
            groups[key] = [peak, 1]

    rows = []
    for key, (thr, counted) in groups.items():
        model, gpu_type, precision, parallelism, gpu_count, itok, otok = key
        rows.append({
            "model_name": model,
            "gpu_type": gpu_type,
            "precision": precision,
            "parallelism": parallelism,
            "gpu_count": gpu_count,
            "input_tokens": itok,
            "output_tokens": otok,
            "total_token_throughput": round(thr, 2),
            "per_gpu_throughput": round(thr / gpu_count, 2),
            "runs_counted": counted,
        })
    rows.sort(key=lambda r: (r["model_name"], -r["per_gpu_throughput"],
                             r["gpu_type"], r["precision"], str(r["parallelism"])))
    # Rank within model only. Per-GPU tokens/sec is comparable between
    # configurations of one model; it is meaningless across model sizes, where a
    # 1.1B model would otherwise "beat" a 70B one.
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["model_name"]] = counts.get(r["model_name"], 0) + 1
        r["rank_within_model"] = counts[r["model_name"]]
    return rows


# ── SQL emission ──────────────────────────────────────────────────────────────

def q(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def jsonb(obj) -> str:
    return q(json.dumps(obj, sort_keys=True)) + "::jsonb"


def pg_array(items: list[str]) -> str:
    inner = ",".join('"' + i.replace('"', '\\"') + '"' for i in items)
    return q("{" + inner + "}")


NS = uuid.UUID("7f3a1c90-5d2e-4b61-9a08-0c4f6e2b1d35")


def _uuid(*parts: str) -> str:
    """Deterministic ids so the corpus is byte-identical across generations."""
    return str(uuid.uuid5(NS, "|".join(parts)))


def emit_sql(runs: list[Run]) -> str:
    out: list[str] = ["BEGIN;"]

    for r in runs:
        wl_id = _uuid("workload", r.run_id)
        node_id = _uuid("node", r.run_id)
        task_id = _uuid("task", r.run_id)
        wl_hid = "wl-" + _uuid("wlhid", r.run_id)[:8]
        machine_hid = "node-" + _uuid("mhid", r.node_ips[0])[:6]
        last_idx = max(1, len(r.sub_runs))
        finished = r.started_at + timedelta(minutes=4 + last_idx * 3)

        out.append(
            "INSERT INTO workloads (id, workload_id, model_name, state, created_at) "
            f"VALUES ({q(wl_id)}::uuid, {q(wl_hid)}, {q(r.recipe.model)}, "
            f"'READY'::workload_state, {q(r.started_at.isoformat())});"
        )
        out.append(
            "INSERT INTO nodes (id, workload_id, machine_id, machine_ip, state, "
            f"created_at) VALUES ({q(node_id)}::uuid, {q(wl_id)}::uuid, "
            f"{q(machine_hid)}, {q(r.node_ips[0])}, 'READY'::node_state, "
            f"{q(r.started_at.isoformat())});"
        )

        # The authoritative record of what was *requested*, as opposed to what
        # ingest ended up storing. Empty for runs predating the feature.
        cfg = {} if r.snapshot_missing else {
            "recipe": r.recipe.name,
            "model_name": r.recipe.model,
            "precision": r.recipe.precision,
            "gpu_count": r.recipe.gpu_count,
            "tensor_parallel_size": r.recipe.tp,
            "pipeline_parallel_size": r.recipe.pp,
            "input_tokens": r.recipe.input_tokens,
            "output_tokens": r.recipe.output_tokens,
            "concurrency_sweep": r.declared_sweep,
            "pipeline_version": r.recipe.pipeline_version,
        }
        out.append(
            "INSERT INTO tasks (id, workload_id, node_id, run_name, task_config, "
            f"status, started_at, completed_at) VALUES ({q(task_id)}::uuid, "
            f"{q(wl_id)}::uuid, {q(node_id)}::uuid, {q(r.run_id)}, {jsonb(cfg)}, "
            f"'success', {q(r.started_at.isoformat())}, {q(finished.isoformat())});"
        )

        for s in r.sub_runs:
            metrics = {
                "total_token_throughput": s.total_token_throughput,
                "mean_ttft_ms": s.mean_ttft_ms,
                "mean_tpot_ms": s.mean_tpot_ms,
                "mean_e2el_ms": s.mean_e2el_ms,
                "server_name": r.recipe.server_name,
                "recipe": r.recipe.name,
                "concurrency": s.concurrency,
            }
            metrics.update(r.blob_extra)
            completed = r.started_at + timedelta(minutes=4 + s.sub_run_index * 3)
            row_id = _uuid("result", r.run_id, str(s.sub_run_index))
            out.append(
                "INSERT INTO benchmark_results ("
                "id, run_id, sub_run_index, model_name, pipeline_version, node_ips, "
                "gpu_type, gpu_count, gpu_model, server_name, precision, "
                "input_tokens, output_tokens, concurrency, parallelism, "
                "workload_type, status, total_token_throughput, mean_ttft_ms, "
                "mean_tpot_ms, mean_e2el_ms, metrics, started_at, completed_at, "
                "duration_seconds) VALUES ("
                f"{q(row_id)}::uuid, {q(r.run_id)}, {s.sub_run_index}, "
                f"{q(r.recipe.model)}, {q(r.rec_pipeline_version)}, "
                f"{pg_array(r.node_ips)}, {q(r.recipe.gpu_type)}, {r.rec_gpu_count}, "
                f"{q(r.recipe.gpu_model)}, {q(r.recipe.server_name)}, "
                f"{q(r.rec_precision)}, {r.rec_input_tokens}, {r.rec_output_tokens}, "
                f"{s.concurrency}, {q(r.rec_parallelism)}, 'llm', 'success', "
                f"{s.total_token_throughput}, {s.mean_ttft_ms}, {s.mean_tpot_ms}, "
                f"{s.mean_e2el_ms}, {jsonb(metrics)}, "
                f"{q(r.started_at.isoformat())}, {q(completed.isoformat())}, "
                f"{(completed - r.started_at).total_seconds()});"
            )

        # Logs. The declared sweep and the launch arguments live here, which is
        # what makes a truncated or mis-recorded run provable for the runs whose
        # task_config snapshot is empty.
        lines = log_lines_for(r, machine_hid)

        for i, line in enumerate(lines):
            out.append(
                "INSERT INTO task_logs (id, task_id, line, logged_at) VALUES ("
                f"{q(_uuid('log', r.run_id, str(i)))}::uuid, {q(task_id)}::uuid, "
                f"{q(line)}, {q((r.started_at + timedelta(seconds=10 * i)).isoformat())});"
            )

    out.append("COMMIT;")
    return "\n".join(out) + "\n"


def emit_records(runs: list[Run]) -> list[dict]:
    """
    The corpus as the documented `validate_runs` input: one record per run,
    carrying the config snapshot, the log lines, and the recorded result rows.

    This is a faithful projection of what the three tables hold -- nothing is
    added and nothing is labelled. It exists so the verifier can exercise the
    agent's validator on a held-out corpus without needing a live database.
    """
    records = []
    for r in runs:
        cfg = {} if r.snapshot_missing else {
            "recipe": r.recipe.name,
            "model_name": r.recipe.model,
            "precision": r.recipe.precision,
            "gpu_count": r.recipe.gpu_count,
            "tensor_parallel_size": r.recipe.tp,
            "pipeline_parallel_size": r.recipe.pp,
            "input_tokens": r.recipe.input_tokens,
            "output_tokens": r.recipe.output_tokens,
            "concurrency_sweep": r.declared_sweep,
            "pipeline_version": r.recipe.pipeline_version,
        }
        lines = log_lines_for(r)

        rows = []
        for s in r.sub_runs:
            metrics = {
                "total_token_throughput": s.total_token_throughput,
                "mean_ttft_ms": s.mean_ttft_ms,
                "mean_tpot_ms": s.mean_tpot_ms,
                "mean_e2el_ms": s.mean_e2el_ms,
                "server_name": r.recipe.server_name,
                "recipe": r.recipe.name,
                "concurrency": s.concurrency,
            }
            metrics.update(r.blob_extra)
            rows.append({
                "sub_run_index": s.sub_run_index,
                "concurrency": s.concurrency,
                "model_name": r.recipe.model,
                "pipeline_version": r.rec_pipeline_version,
                "gpu_type": r.recipe.gpu_type,
                "gpu_count": r.rec_gpu_count,
                "precision": r.rec_precision,
                "input_tokens": r.rec_input_tokens,
                "output_tokens": r.rec_output_tokens,
                "parallelism": r.rec_parallelism,
                "status": "success",
                "total_token_throughput": s.total_token_throughput,
                "mean_ttft_ms": s.mean_ttft_ms,
                "node_ips": list(r.node_ips),
                "started_at": r.started_at.isoformat(),
                "metrics": metrics,
            })

        records.append({
            "run_id": r.run_id,
            "task_config": cfg,
            "log_lines": lines,
            "results": rows,
        })
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--runs", type=int, default=48)
    ap.add_argument("--out-sql", required=True)
    ap.add_argument("--out-truth", required=True)
    ap.add_argument("--out-records", default=None,
                    help="Write the corpus as validate_runs() input records.")
    args = ap.parse_args()

    runs, truth = build_corpus(args.seed, args.runs)
    ids = [r.run_id for r in runs]
    assert len(ids) == len(set(ids)), "run_id collision within corpus"
    truth["expected_leaderboard"] = expected_leaderboard(runs)
    truth["counts"] = {
        "runs": len(runs),
        "result_rows": sum(len(r.sub_runs) for r in runs),
        "defective_runs": sum(1 for r in runs if r.defects),
    }

    if args.out_records:
        with open(args.out_records, "w") as fh:
            json.dump(emit_records(runs), fh, indent=1, sort_keys=True)

    with open(args.out_sql, "w") as fh:
        fh.write(emit_sql(runs))
    with open(args.out_truth, "w") as fh:
        json.dump(truth, fh, indent=2, sort_keys=True)

    print(f"runs={truth['counts']['runs']} "
          f"rows={truth['counts']['result_rows']} "
          f"defective={truth['counts']['defective_runs']} "
          f"leaderboard_entries={len(truth['expected_leaderboard'])}")


if __name__ == "__main__":
    main()
