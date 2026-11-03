# collinear-candidate/leaderboard-integrity-audit

A long-horizon Harbor task. The agent audits a GPU benchmark leaderboard for
runs that are invalid or not comparable, publishes a corrected leaderboard, and
patches the ingest validator so the same defects cannot recur.

Full rationale, fairness audit, verifier design and model-run evidence are in
[`../RUN_REPORT.md`](../RUN_REPORT.md). The decision trail, including rejected
designs and bugs found during development, is in
[`../DESIGN_JOURNAL.md`](../DESIGN_JOURNAL.md).

## Reproduce

```bash
harbor run -p ./leaderboard-integrity-audit -a oracle
harbor run -p ./leaderboard-integrity-audit -a claude -m opus-5-5
harbor view ./jobs
```

Static checks:

```bash
harbor lint  ./leaderboard-integrity-audit
harbor check ./leaderboard-integrity-audit
```

## What is in the environment

A single container, no network, three services on loopback:

| Service | Where | Why |
|---|---|---|
| PostgreSQL 16 | `127.0.0.1:5432` | The corpus: five tables, 53 runs, 407 result rows |
| aistudio-server REST API | `127.0.0.1:8001` | What the MCP tools read through |
| `aistudio-mcp` | `127.0.0.1:8081/mcp` | The platform's own tool server, admin role |

`network_mode = "no-network"` removes every external interface. Docker's `none`
network still provides a loopback device, so the services reach each other while
the task stays completely offline: no registry, index or mirror can perturb a
run or a grade. The database is initialised and seeded during the image build,
so every run starts from a byte-identical data directory.

## Deliverables the agent must produce

1. `/app/audit/findings.json` — per-run defects, from a published code vocabulary
2. `/app/audit/leaderboard.json` — the corrected leaderboard
3. `/app/app/services/result_validator.py` — `validate_runs(records)`, which the
   verifier exercises against a larger corpus the agent has never seen

## Layout

```
task.toml                 Harbor metadata, timeouts, network policy, MCP server
instruction.md            the agent's only briefing
environment/
  Dockerfile              single container, three loopback services
  entrypoint.sh           starts PostgreSQL, API and MCP, then the harness command
  app/                    aistudio-server, vendored (Apache-2.0)
  mcp-server/app/         the MCP tool server, vendored (Apache-2.0)
  gateway/                throwaway signing key, JWKS and agent token
  seed/schema.sql         five-table schema plus gpu_specs and workload_types
  seed/seed.sql           the generated corpus, committed for reproducibility
tests/
  test.sh                 verifier entrypoint, writes /logs/verifier/reward.json
  check_audit.py          four scored dimensions, standard library only
  fixtures/               seed and held-out corpora with ground truth
solution/
  solve.sh                oracle
  result_validator.py     reference validator
  audit.py                derives both artifacts from the database
tools/gen_runs.py         corpus generator; deliberately outside every image
```

## Provenance

Created for this exercise. Not derived from any benchmark, public issue, CTF or
tutorial. `harbor init --include-canary-strings` stamped a canary GUID into the
task files.

The scenario, corpus, defect taxonomy, verifier and oracle are new. The
application source, database schema and MCP tool server are vendored from
[corespan/aistudio-server](https://github.com/corespan/aistudio-server)
(Apache-2.0), authored by this submission's author, pinned at the commit in
`environment/VENDORED_COMMIT`. `LICENSE` and `NOTICE` ship with the vendored
code. No benchmark data is real: every run in the corpus is synthetic.

The signing key and token in `environment/gateway/` are committed on purpose.
They authenticate nothing outside the sandbox — there is no network, and the
only server they address lives in the same container — and committing them is
what lets the task build identically on any machine.
