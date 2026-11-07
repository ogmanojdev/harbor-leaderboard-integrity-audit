"""Grades the release by what an independent re-derivation of the gates found."""
import json, os, traceback

W = {"suite_green": 0.25, "live_ingests": 0.15, "live_appears": 0.20,
     "gpu_type_normalised": 0.05, "chain_single_head": 0.08,
     "chain_builds": 0.09, "chain_no_drift": 0.08, "chain_roundtrip": 0.05,
     "data_intact": 0.03, "fixes_documented": 0.02}
# The suite as the task shipped it. This constant lives in the verifier image,
# which the agent's container cannot reach.
SUITE_SHA = "704eb58eba5af690932689df98e2636fc786e15c226bb532a03de1f8ed61b716"

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

        # The suite is part of the grading contract. If either copy no longer
        # matches what shipped, nothing measured against it is evidence.
        bad = [w for w in ("sha_app", "sha_pristine") if v.get(w) != SUITE_SHA]
        if bad:
            notes.append("TEST SUITE MODIFIED (%s) - scoring 0" % ", ".join(bad))
            v = {}

        # SUITE — every test passing, nothing erroring at collection.
        out["suite_green"] = 1.0 if (v.get("sf", 1) == 0 and v.get("se", 1) == 0
                                     and v.get("sp", 0) >= 100) else 0.0
        # LIVE — a fresh run is accepted, stored, and comes back on the board.
        out["live_ingests"] = 1.0 if v.get("i") == 202 else 0.0
        out["live_appears"] = 1.0 if (v.get("a", 0) and v.get("db", 0)) else 0.0
        out["gpu_type_normalised"] = 1.0 if v.get("gl", 0) else 0.0
        # CHAIN — one head, applies clean, matches the models, round-trips.
        out["chain_single_head"] = 1.0 if v.get("heads") == 1 else 0.0
        out["chain_builds"] = 1.0 if v.get("up") == 1 else 0.0
        out["chain_no_drift"] = 1.0 if v.get("drift") == 0 else 0.0
        out["chain_roundtrip"] = 1.0 if v.get("rt") == 1 else 0.0
        # The historical corpus must survive.
        out["data_intact"] = 1.0 if v.get("hist", 0) >= 300 else 0.0
        out["fixes_documented"] = 1.0 if v.get("fx", 0) > 40 else 0.0

    out["overall"] = round(sum(out[k] * w for k, w in W.items()), 4)
except Exception:
    notes.append(traceback.format_exc(limit=3))

os.makedirs("/logs/verifier", exist_ok=True)
json.dump(out, open("/logs/verifier/reward.json", "w"), indent=2)
open("/logs/verifier/report.txt", "w").write("\n".join(notes) + "\n")
print("\n".join(notes))
