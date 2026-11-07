# collinear-candidate/leaderboard-integrity-audit

A long-horizon Harbor task. The agent audits a GPU benchmark leaderboard for
runs that are invalid or not comparable, publishes a corrected leaderboard, and
patches the ingest validator so the same defects cannot recur.

Full rationale, fairness audit, verifier design, shortcut-resistance analysis
and model-run evidence are in [`../RUN_REPORT.md`](../RUN_REPORT.md).

## Reproduce

The MCP server inside the container verifies a bearer token, and Harbor
resolves `${AISTUDIO_MCP_TOKEN}` in the MCP header from the shell before it
launches. The token ships in this repository, so export it from the file:

```bash
export AISTUDIO_MCP_TOKEN="$(cat leaderboard-integrity-audit/environment/gateway/agent-token.jwt)"

harbor run -p ./leaderboard-integrity-audit -a oracle
harbor run -p ./leaderboard-integrity-audit -a claude-code -m opus-5-5
harbor view ./jobs
```

Nothing secret is involved: the token addresses a server on loopback inside an
offline container, and `tools/mint_gateway_key.py` regenerates a fresh set.
The oracle does not use the MCP server, so it runs without the export.

The registered agent is `claude-code`. To reach the model through a proxy rather
than Anthropic's first-party API, add
`-m anthropic/claude-opus-5.5 --base-url https://openrouter.ai/api`.

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

## Scope of this repository

The submission is the single task directory `leaderboard-integrity-audit/`.
`evidence/` at the repository root holds the target-model trial logs and the
mechanism of two further probe tasks built to test what breaks a frontier
agent; nothing in `evidence/` is a Harbor task directory or offered for grading.
See `../RUN_REPORT.md` section 8.

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

`environment/gateway/` ships the JWKS and the agent's token, but not the
private key that signed them. They authenticate nothing outside the sandbox —
there is no network, and the only server they address lives in the same
container — and committing them is what lets the task build identically on any
machine. The private key is not needed to build or run anything; regenerate a
consistent set with `tools/mint_gateway_key.py` if you want to mint your own.
