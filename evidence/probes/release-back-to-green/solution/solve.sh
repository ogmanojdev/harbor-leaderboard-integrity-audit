#!/bin/bash
# Oracle. Seven defects across three gates that fail for unrelated reasons.
set -euo pipefail
cd /app

# ── CHAIN ─────────────────────────────────────────────────────────────────────

# D1. The revision was rebased onto its grandparent, forking the chain.
sed -i 's|^down_revision = "f0e43419bf9b"$|down_revision = "b1c2d3e4f5a6"|' \
  alembic/versions/c1d2e3f4a5b6_add_server_name_to_benchmark_results.py

# D2. benchmark_results.mean_itl_ms is mapped by the ORM but no revision ever
# created it. The live database was built by the chain, so it lacks the column
# and every SELECT on the table fails. The fix has to be a revision: chain.sh
# rebuilds a database from the revisions alone and compares it to the models.
cat > alembic/versions/c7f1a9d33b20_add_mean_itl_ms_to_benchmark_results.py <<'REV'
"""add mean_itl_ms to benchmark_results

Revision ID: c7f1a9d33b20
Revises: b3c4d5e6f7a8
Create Date: 2026-11-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "c7f1a9d33b20"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "benchmark_results",
        sa.Column("mean_itl_ms", sa.Float(), nullable=True,
                  comment="Mean inter-token latency in milliseconds."),
    )


def downgrade() -> None:
    op.drop_column("benchmark_results", "mean_itl_ms")
REV
alembic upgrade head

# ── LIVE ──────────────────────────────────────────────────────────────────────

# D4. The upsert's conflict target must be the unique constraint, not run_id,
# which is only indexed.
sed -i 's|index_elements=\["run_id"\],|index_elements=["run_id", "sub_run_index"],|' \
  app/routers/ingest.py

# D5. The hardware-validation filter hides every row with a NULL server_name,
# which is every row ingest writes.
python3 - <<'PY'
import pathlib
p = pathlib.Path("/app/app/routers/results.py"); s = p.read_text()
s = s.replace("    # only surface runs that completed hardware validation\n"
              "    conditions.append(BenchmarkResult.server_name.isnot(None))\n", "")
p.write_text(s)
PY

# ── SUITE ─────────────────────────────────────────────────────────────────────

# D6. The mask regex captured three octets instead of two, leaking the third.
python3 - <<'PY'
import pathlib
p = pathlib.Path("/app/app/schemas/benchmark.py"); s = p.read_text()
s = s.replace(r"_IP_RE = re.compile(r'(?<![.\d])(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}(?![.\d])')",
              r"_IP_RE = re.compile(r'(?<![.\d])(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}(?![.\d])')")
p.write_text(s)
PY

# D8. gpu_type has to be normalised on write or the same GPU splits in two.
sed -i 's|"gpu_type": payload.gpu_type,|"gpu_type": payload.gpu_type.lower(),|' \
  app/routers/ingest.py

# D9. The seeder stopped refreshing image_tag on existing workload types.
python3 - <<'PY'
import pathlib
p = pathlib.Path("/app/app/services/catalog_seeder.py"); s = p.read_text()
old = '                existing.description = wt.get("description", "")\n'
assert old in s
s = s.replace(old, old + '                existing.image_tag = wt.get("image_tag")\n')
p.write_text(s)
PY

# D10. build_llm_benchmark_command was reverted to its pre-GCR revision. Restore
# the node env prelude, the llminference image, the results bind-mount, the
# dataset mount, the HF_TOKEN passthrough and the --tp flag.
python3 - <<'PYFIX'
import pathlib
p = pathlib.Path("/app/app/services/manifest_builder.py")
s = p.read_text()
start = '        gpu_count   = config.get("gpu_count", 1)\n'
end = '\n    @staticmethod\n    def build_jupyter_command'
assert s.count(start) == 1 and s.count(end) == 1
body = """        gpu_count     = config.get("gpu_count", 1)
        concurrency   = config.get("concurrency", 32)
        enable_opts   = config.get("enable_optimizations", False)
        max_model_len = config.get("max_model_len")

        tag   = image_tag or settings.WORKLOAD_IMAGE_TAG
        image = "%s/llminference:%s" % (get_workload_registry(), tag)

        container_name = "llmbench-%s" % run_id if run_id else "llmbench"
        rm_cmd = "docker rm -f %s 2>/dev/null || true" % container_name

        bench_args = [
            "--model",            model_name,
            "--output_data_path", "/results/%s" % run_id,
            "--run_name",         run_id or model_name,
            "--tp",               str(gpu_count),
            "--concurrencies",    str(concurrency),
            "--dataset-path",     dataset_path,
        ]
        if max_model_len:
            bench_args += ["--max_model_len", str(max_model_len)]
        if enable_opts:
            bench_args.append("--enable_optimizations")

        dataset_mount = "-v %s:%s" % (dataset_path, dataset_path) if dataset_path else ""
        run_cmd = " ".join(p for p in [
            "docker run --gpus all --rm --name %s" % container_name,
            "--ipc=host",
            "--entrypoint python3",
            "-v $HOME/.cache/huggingface:/root/.cache/huggingface",
            "-v %s:/results" % settings.NODE_RESULTS_PATH,
            dataset_mount,
            _hf_token_flags(),
            image,
            "/llm-inference/benchmark.py",
            " ".join(bench_args),
        ] if p)

        return "%s ; %s && %s" % (_LOAD_NODE_ENV, rm_cmd, run_cmd)
"""
i, j = s.index(start), s.index(end)
p.write_text(s[:i] + body + s[j:])
PYFIX

/app/gates.sh

cat > /app/fixes.md <<'MD'
- alembic/versions/c1d2e3f4a5b6: down_revision pointed at the grandparent, forking the chain into two heads. Restored the parent b1c2d3e4f5a6.
- app/models/benchmark_result.py declares mean_itl_ms but no revision created it, so the live database lacked the column. Added revision c7f1a9d33b20 and upgraded.
- app/routers/ingest.py: upsert conflict target was run_id, which is indexed but not unique, so every ingest raised. Restored (run_id, sub_run_index).
- app/routers/results.py: a hardware-validation filter hid every row with a NULL server_name, i.e. every newly ingested row. Removed it.
- app/schemas/benchmark.py: the IP mask regex captured three octets, so the third octet leaked. Restored the two-octet capture.
- app/routers/ingest.py: gpu_type was stored as sent, splitting 'H100' and 'h100'. Restored .lower().
- app/services/catalog_seeder.py: existing workload types no longer had image_tag refreshed from catalog.json. Restored the assignment.
- app/services/manifest_builder.py: build_llm_benchmark_command had been reverted to a pre-GCR revision - no node env prelude, no /results mount, no HF_TOKEN passthrough, --tensor-parallel-size instead of --tp, and the public vllm image instead of llminference. Rewrote the body.
MD
