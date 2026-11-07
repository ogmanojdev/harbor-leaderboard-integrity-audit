#!/usr/bin/env python3
"""
Applies the task's defects to the vendored source tree.

Run AFTER the database has been built from the pristine migration chain, so the
shipped database sits at head with the historical corpus loaded. Every defect is
an exact-string rewrite that asserts its anchor was found, so a vendored-source
bump cannot silently drop a defect.

Each defect names the gate it breaks:
  CHAIN  — the migration chain / models-vs-migrations agreement
  LIVE   — the running ingest -> leaderboard path
  SUITE  — the pytest suite
Deliberately NOT planted: a bad driver name in the async DSN. It breaks
app.database at import time, so pytest cannot even collect and all three gates
report the same ModuleNotFoundError. One sed clears every gate at once — the
defect makes the task look deep while making it cheap. Defects here must fail
their own gate and leave the others readable.

Also NOT planted: removing the RUNNING -> READY edge from the workload state
machine. No test in the suite exercises that edge and no gate observes it, so
the agent could neither discover it nor verify a fix. A defect has to be
observable through a gate, otherwise it is a guess.

Also NOT planted: dropping the .lower() normalisation from the model-config
lookup in app/catalog.py. Every model_id in catalog.json is already lowercase,
so the call is a no-op and removing it changes nothing any test can see. A
defect has to be exercised by the data, not merely present in the code.
"""
import pathlib
import sys

ROOT = pathlib.Path("/app")
applied = []


def patch(relpath, old, new, defect, gate):
    p = ROOT / relpath
    s = p.read_text()
    if old not in s:
        sys.exit(f"ANCHOR MISSING for {defect} in {relpath}:\n{old!r}")
    if s.count(old) != 1:
        sys.exit(f"ANCHOR AMBIGUOUS for {defect} in {relpath}: {s.count(old)} matches")
    p.write_text(s.replace(old, new))
    applied.append(f"[{gate}] {defect} -> {relpath}")


def patch_span(relpath, start, end, new, defect, gate):
    """Replace everything from `start` up to (not including) `end`."""
    p = ROOT / relpath
    s = p.read_text()
    for marker, label in ((start, "start"), (end, "end")):
        if s.count(marker) != 1:
            sys.exit("%s MARKER not unique for %s in %s: %d matches"
                     % (label.upper(), defect, relpath, s.count(marker)))
    i, j = s.index(start), s.index(end)
    if i >= j:
        sys.exit("MARKERS out of order for %s in %s" % (defect, relpath))
    p.write_text(s[:i] + new + s[j:])
    applied.append("[%s] %s -> %s" % (gate, defect, relpath))


# ── CHAIN ─────────────────────────────────────────────────────────────────────

# D1. A bad rebase pointed this revision at its grandparent instead of its
# parent, leaving the chain with two heads. The shipped database is already at
# head, so the running service is unaffected; only a migration from scratch
# fails. Fix: restore the parent.
patch("alembic/versions/c1d2e3f4a5b6_add_server_name_to_benchmark_results.py",
      'down_revision = "b1c2d3e4f5a6"',
      'down_revision = "f0e43419bf9b"',
      "D1 chain forked: down_revision rebased onto the wrong parent", "CHAIN")

# D2. The ORM grew a column that no revision ever adds. pytest builds its schema
# with Base.metadata.create_all, so the suite cannot see this; the live database
# was built by the chain, so every SELECT on benchmark_results fails against it.
# Fix: author a revision that adds the column, then upgrade.
patch("app/models/benchmark_result.py",
      """    mean_e2el_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Mean end-to-end latency per request in milliseconds.",
    )
""",
      """    mean_e2el_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Mean end-to-end latency per request in milliseconds.",
    )

    mean_itl_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Mean inter-token latency in milliseconds.",
    )
""",
      "D2 model/migration drift: mean_itl_ms mapped but never migrated", "CHAIN")

# ── LIVE ──────────────────────────────────────────────────────────────────────

# D4. The upsert's conflict target was narrowed to run_id, which is indexed but
# not unique, so PostgreSQL rejects every ON CONFLICT and ingest 500s.
patch("app/routers/ingest.py",
      'index_elements=["run_id", "sub_run_index"],',
      'index_elements=["run_id"],',
      "D4 upsert conflict target is not a unique constraint", "LIVE")

# D5. A hardware-validation filter left in the leaderboard query hides every row
# whose server_name is NULL — which is every row ingest writes unless the runner
# supplies one.
patch("app/routers/results.py",
      "    if server_name:\n"
      "        conditions.append(BenchmarkResult.server_name == server_name)\n",
      "    if server_name:\n"
      "        conditions.append(BenchmarkResult.server_name == server_name)\n"
      "    # only surface runs that completed hardware validation\n"
      "    conditions.append(BenchmarkResult.server_name.isnot(None))\n",
      "D5 stale filter hides rows with NULL server_name", "LIVE")

# ── SUITE ─────────────────────────────────────────────────────────────────────

# D6. The masking regex lost a group, so only the final octet is replaced and
# the third octet still leaks.
patch("app/schemas/benchmark.py",
      "_IP_RE = re.compile(r'(?<![.\\d])(\\d{1,3}\\.\\d{1,3})\\.\\d{1,3}\\.\\d{1,3}(?![.\\d])')",
      "_IP_RE = re.compile(r'(?<![.\\d])(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\\.\\d{1,3}(?![.\\d])')",
      "D6 IP mask leaks the third octet", "SUITE")

# D8. gpu_type is stored as the runner sent it, so 'H100' and 'h100' become two
# different GPUs on the leaderboard.
patch("app/routers/ingest.py",
      '"gpu_type": payload.gpu_type.lower(),',
      '"gpu_type": payload.gpu_type,',
      "D8 gpu_type no longer normalised to lowercase", "SUITE")

# D9. The catalog seeder stopped refreshing image_tag, so a released image tag
# never reaches an existing workload type.
patch("app/services/catalog_seeder.py",
      '                existing.image_tag = wt.get("image_tag")\n',
      "",
      "D9 catalog seeder no longer refreshes image_tag", "SUITE")

# D10. The merge reverted this method to its pre-GCR revision: it still shells
# out to docker run with the right model, but it predates the node env prelude,
# the results bind-mount, the --tp flag and the llminference image. Six tests
# pin the current behaviour and the method's own docstring still documents it,
# so the contract is published; the body has to be written back.
_D10_OLD_BODY = '''        gpu_count   = config.get("gpu_count", 1)
        concurrency = config.get("concurrency", 32)

        container_name = "llmbench-%s" % run_id if run_id else "llmbench"
        rm_cmd = "docker rm -f %s 2>/dev/null || true" % container_name

        bench_args = [
            "--model",                model_name,
            "--run_name",             run_id or model_name,
            "--tensor-parallel-size", str(gpu_count),
            "--concurrencies",        str(concurrency),
        ]

        run_cmd = " ".join([
            "docker run --gpus all --rm --name %s" % container_name,
            "--ipc=host",
            "-v $HOME/.cache/huggingface:/root/.cache/huggingface",
            "vllm/vllm-openai:latest",
            "/llm-inference/benchmark.py",
            " ".join(bench_args),
        ])

        return "%s && %s" % (rm_cmd, run_cmd)
'''

patch_span("app/services/manifest_builder.py",
           '        gpu_count     = config.get("gpu_count", 1)\n',
           '\n    @staticmethod\n    def build_jupyter_command',
           _D10_OLD_BODY,
           "D10 manifest builder reverted to its pre-GCR revision", "SUITE")

print("\n".join(applied))
print(f"\n{len(applied)} defects applied")
