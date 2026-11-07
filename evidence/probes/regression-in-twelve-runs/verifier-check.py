"""
Grade the claim, not the wording.

The submitted condition is evaluated over all 1152 configurations and compared
against the true affected set, so a predicate that names the right fields but
the wrong boundary scores partially, and one that is exactly right scores full.
Budget is read from the ledger the agent could not write to.
"""
import itertools, json, os, traceback

MODELS = ["llama31-70b", "llama33-70b", "deepseek-r1-70b", "qwen25-32b"]
GPUS = ["h100", "mi210", "rtx5090", "t4"]
PRECISIONS = ["bf16", "fp8", "fp16"]
TPS = [1, 2, 4, 8]
DRIVERS = ["550", "560", "570"]
CHUNKED = [0, 1]
BUDGET_RUNS = 10


def truth(c):
    return c["precision"] == "fp8" and c["tp"] >= 4 and c["driver"] == "570"


def grid():
    for m, g, p, t, d, k in itertools.product(MODELS, GPUS, PRECISIONS, TPS, DRIVERS, CHUNKED):
        yield {"model": m, "gpu": g, "precision": p, "tp": t, "driver": d,
               "chunked_prefill": k}


OPS = {
    "eq":  lambda a, b: a == b,
    "ne":  lambda a, b: a != b,
    "lt":  lambda a, b: _num(a) < _num(b),
    "lte": lambda a, b: _num(a) <= _num(b),
    "gt":  lambda a, b: _num(a) > _num(b),
    "gte": lambda a, b: _num(a) >= _num(b),
}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def evaluate(cond, c):
    for cl in cond.get("all_of", []):
        f, op, v = cl.get("field"), cl.get("op"), cl.get("value")
        if f not in c or op not in OPS:
            return False
        a = c[f]
        if op in ("eq", "ne"):
            if not OPS[op](str(a), str(v)):
                return False
        elif not OPS[op](a, v):
            return False
    return True


def find(name):
    for root in ("/logs/artifacts", "/app", "/opt/bench-public", "/opt", "/logs", "/tests"):
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            if name in files:
                return os.path.join(dirpath, name)
    return None


out = {"overall": 0.0, "condition_exact": 0.0, "condition_f1": 0.0,
       "within_budget": 0.0, "evidence_present": 0.0}
notes = []
for _r in ("/logs/artifacts", "/app", "/logs"):
    if os.path.isdir(_r):
        notes.append(f"{_r}: {sorted(os.listdir(_r))[:12]}")
try:
    fp = find("finding.json")
    if not fp:
        notes.append("no finding.json")
    else:
        doc = json.load(open(fp))
        cond = doc.get("condition") or {}
        pred = {i for i, c in enumerate(grid()) if evaluate(cond, c)}
        real = {i for i, c in enumerate(grid()) if truth(c)}
        tp, fpos, fn = len(pred & real), len(pred - real), len(real - pred)
        f1 = 0.0 if tp == 0 else 2 * tp / (2 * tp + fpos + fn)
        out["condition_f1"] = round(f1, 4)
        out["condition_exact"] = 1.0 if (fpos == 0 and fn == 0) else 0.0
        out["evidence_present"] = 1.0 if str(doc.get("evidence", "")).strip() else 0.0
        notes.append(f"predicted={len(pred)} true={len(real)} tp={tp} fp={fpos} fn={fn} f1={f1:.3f}")
        notes.append(f"clauses={len(cond.get('all_of', []))}")

    lp = find("ledger.json")
    if lp:
        led = json.load(open(lp))
        n = len(led.get("runs", []))
        out["within_budget"] = 1.0 if n <= BUDGET_RUNS else 0.0
        notes.append(f"runs_used={n} of {BUDGET_RUNS}")
    else:
        notes.append("no ledger.json; budget unverifiable")

    out["overall"] = round(0.55 * out["condition_exact"] + 0.20 * out["condition_f1"]
                           + 0.20 * out["within_budget"] + 0.05 * out["evidence_present"], 4)
except Exception:
    notes.append(traceback.format_exc(limit=2))

os.makedirs("/logs/verifier", exist_ok=True)
json.dump(out, open("/logs/verifier/reward.json", "w"), indent=2)
open("/logs/verifier/report.txt", "w").write("\n".join(notes) + "\n")
print("\n".join(notes))
