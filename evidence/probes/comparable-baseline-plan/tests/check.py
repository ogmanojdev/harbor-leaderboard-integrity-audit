"""Grades the plan by applying it to the corpus and measuring the floor."""
import json, os, traceback

W = {"plan_parses": 0.05, "schema_valid": 0.10, "known_entities": 0.05,
     "allowed_concurrencies": 0.05, "coverage": 0.45, "within_budget": 0.25,
     "notes_written": 0.05}
out = {k: 0.0 for k in W}
out["overall"] = 0.0
notes = []


def find(name):
    for root in ("/logs/artifacts", "/app", "/opt", "/logs", "/tests"):
        if os.path.isdir(root):
            for d, _, f in os.walk(root):
                if name in f:
                    return os.path.join(d, name)
    return None


try:
    vp = find("verify.json") or find(".verify.json")
    if not vp:
        notes.append("no verify.json — the collect hook produced nothing")
    else:
        v = json.load(open(vp))
        notes.append("independent re-derivation: %s" % v)
        for k in ("plan_parses", "schema_valid", "known_entities",
                  "allowed_concurrencies", "coverage", "within_budget"):
            out[k] = 1.0 if v.get(k) == 1 else 0.0
        if v.get("coverage") != 1:
            notes.append("floor not met: %s of %s configurations still short, "
                         "worst short by %s peer(s)"
                         % (v.get("groups_short"), v.get("groups_total"),
                            v.get("worst_shortfall")))
        if v.get("within_budget") != 1:
            notes.append("budget: %s sweeps planned, limit is 23" % v.get("n_sweeps"))
    nt = find("plan_notes.md")
    if nt and len(open(nt).read().strip()) > 40:
        out["notes_written"] = 1.0
    out["overall"] = round(sum(out[k] * w for k, w in W.items()), 4)
except Exception:
    notes.append(traceback.format_exc(limit=3))

os.makedirs("/logs/verifier", exist_ok=True)
json.dump(out, open("/logs/verifier/reward.json", "w"), indent=2)
open("/logs/verifier/report.txt", "w").write("\n".join(notes) + "\n")
print("\n".join(notes))
