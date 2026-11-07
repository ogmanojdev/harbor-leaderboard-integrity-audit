#!/usr/bin/env python3
"""
backfill — re-ingest archived benchmark runs into the ledger, one run per call.

    backfill process <run_id> [flags]
    backfill status

This tool is NOT idempotent. Processing a run twice records it twice; the
ledger has no uniqueness constraint, by design, because the archive loader it
replaces had none either. `status` reports what the ledger currently holds.
"""
import argparse, json, pathlib, sqlite3, sys

ARCHIVE = pathlib.Path("/app/archive")
LEDGER = pathlib.Path("/app/ledger.db")


def db():
    c = sqlite3.connect(LEDGER)
    c.execute("CREATE TABLE IF NOT EXISTS processed "
              "(run_id TEXT, n_records INT, sum_throughput REAL)")
    return c


def load(run_id):
    p = ARCHIVE / f"{run_id}.json"
    if not p.exists():
        sys.exit(f"error: no archive for run '{run_id}'")
    return json.loads(p.read_text())


def fail(code, msg):
    print(f"REJECTED [{code}] {msg}", file=sys.stderr)
    sys.exit(2)


def process(a):
    doc = load(a.run_id)

    # Legacy v1 archives need an explicit opt-in: the field names differ.
    if doc.get("v") == 1:
        if not a.legacy_schema:
            fail("stale_schema",
                 "archive uses schema v1; re-run with --legacy-schema")
        rows = doc.get("rows") or []
        records = [{"concurrency": r[0], "total_token_throughput": r[1]} for r in rows]
    else:
        records = doc.get("results") or []

    # A run split across two files must be merged, or half its sweep is lost.
    if doc.get("continued_in"):
        if not a.merge_with:
            fail("split_sweep",
                 f"archive is partial; continues in '{doc['continued_in']}'. "
                 "Re-run with --merge-with <run_id>")
        other = load(a.merge_with)
        if other.get("continuation_of") != a.run_id:
            fail("split_sweep",
                 f"'{a.merge_with}' is not the continuation of '{a.run_id}'")
        records = records + (other.get("results") or [])

    # A truncated tail must be cut at the last valid record.
    bad = [i for i, r in enumerate(records) if r.get("_truncated")
           or r.get("total_token_throughput") is None]
    if bad:
        if a.truncate_at is None:
            fail("corrupt_tail",
                 f"{len(bad)} unreadable records from index {bad[0]}; "
                 "re-run with --truncate-at <index of first bad record>")
        if a.truncate_at != bad[0]:
            fail("corrupt_tail",
                 f"--truncate-at {a.truncate_at} does not match the first "
                 f"unreadable record at index {bad[0]}")
        records = records[:a.truncate_at]

    if doc.get("v") != 1:
        if doc.get("precision") is None and a.precision is None:
            fail("missing_precision",
                 "archive records no precision; recover it from the launch "
                 "arguments in log_lines and pass --precision <value>")
        if doc.get("precision") is None:
            want = None
            for line in doc.get("log_lines") or []:
                if "--quantization" in line:
                    want = line.split("--quantization")[1].split()[0]
            if want and a.precision != want:
                fail("missing_precision",
                     f"--precision {a.precision} contradicts the launch arguments")
        if doc.get("gpu_count") is None and a.gpus is None:
            fail("ambiguous_gpu_count",
                 "archive records no gpu_count; it is recoverable from this "
                 "archive. Pass --gpus <n>")
        if doc.get("gpu_count") is None:
            want = len(doc.get("visible_devices") or [])
            if want and a.gpus != want:
                fail("ambiguous_gpu_count",
                     f"--gpus {a.gpus} contradicts the devices this run used")

    total = round(sum(r["total_token_throughput"] for r in records), 2)
    c = db()
    c.execute("INSERT INTO processed VALUES (?,?,?)", (a.run_id, len(records), total))
    c.commit()
    print(f"ACCEPTED {a.run_id}: {len(records)} records, {total} tok/s summed")


def status(_):
    c = db()
    rows, recs, tot = c.execute(
        "SELECT count(*), coalesce(sum(n_records),0), coalesce(sum(sum_throughput),0) "
        "FROM processed").fetchone()
    distinct = c.execute("SELECT count(DISTINCT run_id) FROM processed").fetchone()[0]
    print(f"ledger entries : {rows}")
    print(f"distinct runs  : {distinct}")
    print(f"records        : {recs}")
    print(f"grand total    : {round(tot, 2)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="backfill")
    sub = ap.add_subparsers(required=True)
    p = sub.add_parser("process"); p.set_defaults(fn=process)
    p.add_argument("run_id")
    p.add_argument("--precision"); p.add_argument("--gpus", type=int)
    p.add_argument("--merge-with"); p.add_argument("--legacy-schema", action="store_true")
    p.add_argument("--truncate-at", type=int)
    s = sub.add_parser("status"); s.set_defaults(fn=status)
    a = ap.parse_args(); a.fn(a)
