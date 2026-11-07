"""Minimal prototype verifier: did the ledger land in exactly the right state?"""
import json, os, sqlite3, traceback
SKIP = {"/proc","/sys","/dev","/opt/node","/usr","/lib","/bin","/sbin","/etc","/var/lib"}

def _scan():
    hits = {}
    for root in ("/logs", "/tests", "/app", "/artifacts", "/"):
        if not os.path.isdir(root):
            continue
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if os.path.join(dirpath, d) not in SKIP]
            if dirpath.count(os.sep) > 5:
                dirs[:] = []
            for f in files:
                if f in ("ledger.db", "report.json"):
                    hits.setdefault(f, os.path.join(dirpath, f))
        if len(hits) == 2:
            break
    return hits

TARGET = {"runs": 150, "entries": 150, "records": 1182, "total": 1288996.01}

HITS = _scan()

def find(name):
    return HITS.get(name)

out = {"overall": 0.0, "exactly_once": 0.0, "totals_match": 0.0, "report_present": 0.0}
notes = [f"artifact scan: {HITS or 'nothing found'}",
         f"/logs contains: {sorted(os.listdir('/logs')) if os.path.isdir('/logs') else 'absent'}"]
try:
    db = find("ledger.db")
    if db:
        c = sqlite3.connect(db)
        entries, recs, tot = c.execute(
            "SELECT count(*), coalesce(sum(n_records),0), coalesce(sum(sum_throughput),0) "
            "FROM processed").fetchone()
        runs = c.execute("SELECT count(DISTINCT run_id) FROM processed").fetchone()[0]
        dupes = c.execute("SELECT count(*) FROM (SELECT run_id FROM processed "
                          "GROUP BY run_id HAVING count(*)>1)").fetchone()[0]
        notes.append(f"entries={entries} distinct={runs} records={recs} total={round(tot,2)} dupes={dupes}")
        out["exactly_once"] = 1.0 if (entries == TARGET["entries"] and runs == TARGET["runs"]
                                      and dupes == 0) else 0.0
        out["totals_match"] = 1.0 if (recs == TARGET["records"]
                                      and abs(tot - TARGET["total"]) < 0.5) else 0.0
    else:
        notes.append("no ledger.db collected")
    rp = find("report.json")
    if rp:
        json.load(open(rp)); out["report_present"] = 1.0
    out["overall"] = round(0.5*out["exactly_once"] + 0.4*out["totals_match"]
                           + 0.1*out["report_present"], 4)
except Exception:
    notes.append(traceback.format_exc(limit=2))
os.makedirs("/logs/verifier", exist_ok=True)
json.dump(out, open("/logs/verifier/reward.json", "w"), indent=2)
open("/logs/verifier/report.txt", "w").write("\n".join(notes) + "\n")
print("\n".join(notes))
