"""
Verifier for the leaderboard-integrity-audit task.

Standard library only, by design: the task runs with network_mode="no-network",
so grading must not depend on fetching anything. Five independently scored
dimensions are combined into a weighted overall reward.

  functional_correctness (0.35)  the submitted validator, run against a larger
                                 corpus it has never seen, macro-F1 over classes
  constraint_satisfaction (0.25)  the corrected leaderboard, compared exactly
  robustness (0.15)               specificity on valid runs, scaled by recall,
                                  plus a determinism check
  artifact_quality (0.10)         findings over the local corpus, macro-F1
  completeness (0.15)             every defect class reported, and an exact
                                  leaderboard -- scored as a yes or no

The held-out corpus is what makes shallow solutions fail: a validator that
recognises run identifiers, or hardcodes counts from the local database,
scores zero on the largest dimension while still looking correct locally.
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import sys
import traceback

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(TESTS_DIR, "fixtures")

# In separate verifier mode the declared artifacts are collected from the
# agent's container and uploaded here. The in-place paths are kept as a
# fallback so the checker also runs correctly in a shared environment.
ARTIFACTS_DIR = os.environ.get("HARBOR_ARTIFACTS_DIR", "/logs/artifacts")


def _first_existing(*candidates: str) -> str:
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


FINDINGS_PATH = _first_existing(
    os.path.join(ARTIFACTS_DIR, "audit", "findings.json"),
    "/app/audit/findings.json",
)
LEADERBOARD_PATH = _first_existing(
    os.path.join(ARTIFACTS_DIR, "audit", "leaderboard.json"),
    "/app/audit/leaderboard.json",
)
VALIDATOR_PATH = _first_existing(
    os.path.join(ARTIFACTS_DIR, "result_validator.py"),
    "/app/app/services/result_validator.py",
)

VOCABULARY = {
    "missing_parallelism", "defaulted_precision", "defaulted_gpu_count",
    "zero_token_config", "duplicate_logical_run", "truncated_sweep",
    "clock_skew_duration", "status_not_in_enum", "unknown_pipeline_version",
}

WEIGHTS = {
    "functional_correctness": 0.35,
    "constraint_satisfaction": 0.25,
    "robustness": 0.15,
    "artifact_quality": 0.10,
    "completeness": 0.15,
}

notes: list[str] = []


def note(msg: str) -> None:
    notes.append(msg)
    print(msg, flush=True)


def load_json(path: str):
    with open(path) as fh:
        return json.load(fh)


def f1(got: set, exp: set) -> tuple[float, int, int, int]:
    tp = len(got & exp)
    fp = len(got - exp)
    fn = len(exp - got)
    if tp == 0:
        return 0.0, tp, fp, fn
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    return 2 * precision * recall / (precision + recall), tp, fp, fn


def macro_f1(got: set, exp: set) -> tuple[float, int, int, int]:
    """
    F1 averaged over defect classes, not over (run, defect) pairs.

    The task is to find every class of defect. Micro-averaging lets a whole
    class be missed for roughly a tenth of the score, because each class covers
    only two or three runs; averaging over classes makes missing one cost a
    sixth of the dimension, which is what the instruction actually asks for.

    A class that does not occur and was not reported is skipped. Reporting a
    class that does not occur scores zero for that class, so inventing defects
    is not free.
    """
    scores = []
    for code in sorted(VOCABULARY):
        g = {p for p in got if p[1] == code}
        e = {p for p in exp if p[1] == code}
        if not g and not e:
            continue
        if not e:
            scores.append(0.0)
            continue
        scores.append(f1(g, e)[0])
    overall = sum(scores) / len(scores) if scores else 0.0
    tp = len(got & exp)
    return overall, tp, len(got - exp), len(exp - got)


class Timeout(Exception):
    pass


def _alarm(_sig, _frm):
    raise Timeout()


def load_validator():
    """Import the submitted validator. Never let a bad module kill the grade."""
    if not os.path.isfile(VALIDATOR_PATH):
        note(f"FAIL validator missing at {VALIDATOR_PATH}")
        return None
    try:
        spec = importlib.util.spec_from_file_location("submitted_validator",
                                                      VALIDATOR_PATH)
        mod = importlib.util.module_from_spec(spec)
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(120)
        spec.loader.exec_module(mod)
        signal.alarm(0)
    except Exception:
        note("FAIL validator raised on import:\n" + traceback.format_exc(limit=3))
        return None
    fn = getattr(mod, "validate_runs", None)
    if not callable(fn):
        note("FAIL validator does not expose a callable validate_runs")
        return None
    return fn


def run_validator(fn, records):
    try:
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(300)
        result = fn(records)
        signal.alarm(0)
    except Timeout:
        note("FAIL validate_runs exceeded its time budget")
        return None
    except Exception:
        signal.alarm(0)
        note("FAIL validate_runs raised:\n" + traceback.format_exc(limit=3))
        return None
    if not isinstance(result, dict):
        note(f"FAIL validate_runs returned {type(result).__name__}, expected dict")
        return None
    return result


def pairs_from(mapping) -> set:
    out = set()
    for run_id, codes in (mapping or {}).items():
        for code in codes or []:
            out.add((str(run_id), str(code)))
    return out


def expected_pairs(truth) -> set:
    return {(r, d) for r, i in truth["runs"].items() for d in i["defects"]}


# ── Dimension 1: does the validator generalise? ───────────────────────────────
def score_functional(fn) -> float:
    if fn is None:
        return 0.0
    records = load_json(os.path.join(FIXTURES, "heldout_records.json"))
    truth = load_json(os.path.join(FIXTURES, "heldout_truth.json"))
    result = run_validator(fn, records)
    if result is None:
        return 0.0

    got = pairs_from(result)
    bad = {c for _, c in got} - VOCABULARY
    if bad:
        note(f"WARN codes outside the published vocabulary ignored: {sorted(bad)}")
        got = {(r, c) for r, c in got if c in VOCABULARY}

    score, tp, fp, fn_ = macro_f1(got, expected_pairs(truth))
    note(f"functional_correctness: held-out macro-F1={score:.3f} "
         f"(tp={tp} fp={fp} fn={fn_}) over {len(records)} unseen runs")
    return score


# ── Dimension 2: is the corrected leaderboard right? ──────────────────────────
def _norm(entry: dict) -> tuple:
    return (
        str(entry.get("model_name")), str(entry.get("gpu_type")),
        str(entry.get("precision")), str(entry.get("parallelism")),
        int(entry.get("gpu_count") or 0), int(entry.get("input_tokens") or 0),
        int(entry.get("output_tokens") or 0),
        round(float(entry.get("total_token_throughput") or 0.0), 2),
        round(float(entry.get("per_gpu_throughput") or 0.0), 2),
        int(entry.get("rank_within_model") or 0),
        int(entry.get("runs_counted") or 0),
    )


def score_leaderboard() -> float:
    score_leaderboard.last_exact = False
    path = LEADERBOARD_PATH
    if not os.path.isfile(path):
        note("FAIL leaderboard.json missing")
        return 0.0
    try:
        entries = load_json(path).get("entries")
    except Exception:
        note("FAIL leaderboard.json is not valid JSON")
        return 0.0
    if not isinstance(entries, list):
        note("FAIL leaderboard.json has no 'entries' list")
        return 0.0

    truth = load_json(os.path.join(FIXTURES, "seed_truth.json"))
    expected = truth["expected_leaderboard"]
    try:
        got = {_norm(e) for e in entries}
    except Exception:
        note("FAIL leaderboard entries malformed")
        return 0.0
    exp = {_norm(e) for e in expected}

    score, tp, fp, fn_ = f1(got, exp)
    score_leaderboard.last_exact = (fp == 0 and fn_ == 0 and tp == len(exp))
    note(f"constraint_satisfaction: leaderboard F1={score:.3f} "
         f"(correct={tp} spurious={fp} missing={fn_} of {len(exp)} expected)")
    return score


# ── Dimension 3: does it stay quiet on healthy runs, and behave? ──────────────
def score_robustness(fn) -> float:
    if fn is None:
        return 0.0
    records = load_json(os.path.join(FIXTURES, "heldout_records.json"))
    truth = load_json(os.path.join(FIXTURES, "heldout_truth.json"))
    valid_ids = {r for r, i in truth["runs"].items() if not i["defects"]}

    first = run_validator(fn, records)
    if first is None:
        return 0.0
    flagged_valid = {r for r, c in pairs_from(first) if r in valid_ids}
    specificity = 1.0 - (len(flagged_valid) / len(valid_ids) if valid_ids else 0)

    # Specificity alone is vacuous: a validator that flags nothing at all scores
    # a perfect 1.0 for never making a mistake. Credit is therefore scaled by
    # how much the validator actually detected, so restraint only counts when
    # there is something to be restrained about. Full credit from half recall up.
    exp = expected_pairs(truth)
    got = pairs_from(first)
    recall = len(got & exp) / len(exp) if exp else 0.0
    engagement = min(1.0, recall / 0.5)

    note(f"robustness: specificity={specificity:.3f} "
         f"({len(flagged_valid)} of {len(valid_ids)} healthy runs wrongly flagged), "
         f"held-out recall={recall:.3f}, engagement={engagement:.3f}")

    second = run_validator(fn, records)
    deterministic = second is not None and pairs_from(second) == pairs_from(first)
    if not deterministic:
        note("robustness: validate_runs is not deterministic across calls")

    return max(0.0, specificity) * engagement * (1.0 if deterministic else 0.5)


# ── Dimension 4: are the reported findings right for this database? ───────────
def score_findings() -> float:
    path = FINDINGS_PATH
    if not os.path.isfile(path):
        note("FAIL findings.json missing")
        return 0.0
    try:
        findings = load_json(path).get("findings")
    except Exception:
        note("FAIL findings.json is not valid JSON")
        return 0.0
    if not isinstance(findings, list):
        note("FAIL findings.json has no 'findings' list")
        return 0.0

    got = set()
    for item in findings:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("run_id", ""))
        for code in item.get("defects") or []:
            if code in VOCABULARY:
                got.add((rid, str(code)))

    truth = load_json(os.path.join(FIXTURES, "seed_truth.json"))
    score, tp, fp, fn_ = macro_f1(got, expected_pairs(truth))
    note(f"artifact_quality: findings macro-F1={score:.3f} (tp={tp} fp={fp} fn={fn_})")
    return score


# ── Dimension 5: was the audit actually finished? ────────────────────────────
def score_completeness(validator) -> float:
    """
    One question, answered yes or no: is the audit complete?

    Partial credit across the other four dimensions means a submission that
    misses an entire class of defect still scores near 0.9, because each class
    covers only two or three of sixteen runs. But an audit that overlooks a
    whole category of integrity problem has not done the job, however many
    individual runs it got right. This dimension says so plainly.

    Both halves must hold: every defect class present in the corpus is reported
    at least once, and the corrected leaderboard matches exactly.
    """
    if validator is None:
        note("completeness: no validator")
        return 0.0
    records = load_json(os.path.join(FIXTURES, "heldout_records.json"))
    truth = load_json(os.path.join(FIXTURES, "heldout_truth.json"))
    result = run_validator(validator, records)
    if result is None:
        return 0.0

    expected_classes = {d for i in truth["runs"].values() for d in i["defects"]}
    found_classes = {c for _, c in pairs_from(result) if c in VOCABULARY}
    missed = sorted(expected_classes - found_classes)

    leaderboard_exact = score_leaderboard.last_exact

    if missed:
        note(f"completeness: defect classes never reported: {missed}")
    if not leaderboard_exact:
        note("completeness: corrected leaderboard is not exact")
    complete = not missed and leaderboard_exact
    note(f"completeness: {'audit complete' if complete else 'audit incomplete'}")
    return 1.0 if complete else 0.0


def main() -> int:
    validator = load_validator()

    scores = {
        "functional_correctness": score_functional(validator),
        "constraint_satisfaction": score_leaderboard(),
        "robustness": score_robustness(validator),
        "artifact_quality": score_findings(),
    }
    scores["completeness"] = score_completeness(validator)
    overall = sum(scores[k] * w for k, w in WEIGHTS.items())

    # Harbor requires every value in reward.json to be numeric, so the
    # human-readable diagnostics go to a sibling file (and to stdout, which
    # Harbor captures as test-stdout.txt).
    payload = {"overall": round(overall, 4),
               **{k: round(v, 4) for k, v in scores.items()}}

    os.makedirs("/logs/verifier", exist_ok=True)
    with open("/logs/verifier/reward.json", "w") as fh:
        json.dump(payload, fh, indent=2)
    with open("/logs/verifier/report.txt", "w") as fh:
        fh.write("\n".join(notes) + "\n")

    note(f"OVERALL {overall:.4f}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/reward.json", "w") as fh:
            json.dump({"overall": 0.0, "functional_correctness": 0.0,
                       "constraint_satisfaction": 0.0, "robustness": 0.0,
                       "artifact_quality": 0.0, "completeness": 0.0},
                      fh, indent=2)
        sys.exit(0)
