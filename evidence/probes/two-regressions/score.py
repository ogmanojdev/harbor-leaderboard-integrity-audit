"""Protected scoring core. Owned by root, 0700 — the agent cannot read this."""
import hashlib, json, os, pathlib, sys

LEDGER = pathlib.Path("/opt/bench/ledger.json")
# World-readable mirror so the run count can be collected and audited. The
# directory is root-owned and not writable by the agent, so it cannot be edited.
PUBLIC = pathlib.Path("/opt/bench-public/ledger.json")
COST_PER_RUN = 45
BUDGET = 720                      # sixteen runs

MODELS = ["llama31-70b", "llama33-70b", "deepseek-r1-70b", "qwen25-32b"]
GPUS = ["h100", "mi210", "rtx5090", "t4"]
PRECISIONS = ["bf16", "fp8", "fp16"]
TPS = [1, 2, 4, 8]
DRIVERS = ["550", "560", "570"]
CHUNKED = [0, 1]

BASE = {"llama31-70b": 1180, "llama33-70b": 1120, "deepseek-r1-70b": 980, "qwen25-32b": 1640}
GPU_MULT = {"h100": 1.0, "mi210": 0.42, "rtx5090": 0.68, "t4": 0.09}
PREC_MULT = {"bf16": 1.0, "fp8": 1.62, "fp16": 0.95}


def regressed(c) -> bool:
    """
    Two independent regressions. Neither is visible from an anchor inside the
    other: ablating the driver tells you nothing about the second, and ablating
    chunked_prefill tells you nothing about the first.
    """
    a = c["precision"] == "fp8" and c["tp"] >= 4 and c["driver"] == "570"
    b = c["gpu"] == "mi210" and c["chunked_prefill"] == 1 and c["tp"] >= 4
    return a or b


def clean_throughput(c) -> float:
    t = BASE[c["model"]] * GPU_MULT[c["gpu"]] * PREC_MULT[c["precision"]]
    t *= (c["tp"] ** 0.82)
    t *= 1.04 if c["chunked_prefill"] else 1.0
    h = int(hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()[:8], 16)
    t *= 1.0 + ((h % 2000) / 1000.0 - 1.0) * 0.015
    return t


def throughput(c) -> float:
    t = BASE[c["model"]] * GPU_MULT[c["gpu"]] * PREC_MULT[c["precision"]]
    t *= (c["tp"] ** 0.82)
    t *= 1.04 if c["chunked_prefill"] else 1.0
    # Deterministic per-config variation, so numbers look measured, not synthetic.
    h = int(hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()[:8], 16)
    t *= 1.0 + ((h % 2000) / 1000.0 - 1.0) * 0.015
    if regressed(c):
        t *= 0.55
    return round(t, 2)


def ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"runs": [], "spent": 0}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "budget":
        d = ledger()
        print(f"budget       : {BUDGET} GPU-minutes")
        print(f"spent        : {d['spent']}")
        print(f"remaining    : {BUDGET - d['spent']}")
        print(f"runs         : {len(d['runs'])} (each costs {COST_PER_RUN})")
        return
    if cmd != "run":
        sys.exit("usage: bench run --model M --gpu G --precision P --tp N "
                 "--driver D --chunked-prefill 0|1 | bench budget")
    kv = {}
    args = sys.argv[2:]
    for i in range(0, len(args) - 1, 2):
        kv[args[i].lstrip("-").replace("-", "_")] = args[i + 1]
    try:
        c = {"model": kv["model"], "gpu": kv["gpu"], "precision": kv["precision"],
             "tp": int(kv["tp"]), "driver": str(kv["driver"]),
             "chunked_prefill": int(kv.get("chunked_prefill", 0))}
    except KeyError as e:
        sys.exit(f"error: missing required option {e}")
    for field, allowed in (("model", MODELS), ("gpu", GPUS), ("precision", PRECISIONS),
                           ("tp", TPS), ("driver", DRIVERS), ("chunked_prefill", CHUNKED)):
        if c[field] not in allowed:
            sys.exit(f"error: {field}={c[field]!r} not in {allowed}")
    d = ledger()
    if d["spent"] + COST_PER_RUN > BUDGET:
        sys.exit(f"error: insufficient budget ({BUDGET - d['spent']} GPU-minutes "
                 f"left, a run costs {COST_PER_RUN}). No run was performed.")
    d["spent"] += COST_PER_RUN
    d["runs"].append(c)
    LEDGER.write_text(json.dumps(d))
    PUBLIC.write_text(json.dumps(d))
    os.chmod(PUBLIC, 0o644)
    print(f"run complete  config={json.dumps(c, sort_keys=True)}")
    obs = throughput(c)
    ratio = round(obs / clean_throughput(c), 3)
    print(f"throughput    {obs} tok/s")
    print(f"vs baseline   {ratio}x  ({'REGRESSED' if ratio < 0.9 else 'normal'})")
    print(f"cost          {COST_PER_RUN} GPU-minutes "
          f"({BUDGET - d['spent']} remaining)")


if __name__ == "__main__":
    main()
