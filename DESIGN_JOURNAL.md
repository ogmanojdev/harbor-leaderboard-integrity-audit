# Design journal

Running log of decisions, dead ends, and findings. Kept because the task design
matters more than the task artifacts, and most of the reasoning is invisible in
the finished directory.

---

## 2026-11-02 — Candidate directions considered

Four directions were sketched before committing. Summarised with why each was
kept or dropped.

| # | Direction | Target failure mode | Verdict |
|---|-----------|--------------------|---------|
| A | Reproducibility forensics: pipeline with N planted nondeterminism sources, must become byte-reproducible under perturbed env | Enumerate-all-N; measuring vs. reasoning | Strong, held in reserve |
| B | Crash-safe migration: verifier SIGKILLs the migration at random points, re-runs, demands idempotency | Agents never test their own crash paths | Strong, held in reserve |
| C | MCP tool forensics against a service whose behaviour has drifted from its docs | Trusting documentation over observed behaviour | **Chosen**, then substantially revised — see below |
| D | Ledger forensics: corrupted event-sourced ledger, repair must generalise to a held-out log | State tracking; overfitting to the sample | Dropped — overlaps D with C's verifier design, less novel |

Chose C on novelty: Collinear explicitly names MCP tool calling as a domain of
interest, and an MCP-shaped submission should be rarer than the SWE-bench-flavoured
default among 1000+ assignments.

### Rejected: the "Meridian Payouts" scenario

C was first drafted as a fictional vendor payouts API with six planted
doc-vs-reality drifts (pagination cap, exclusive date bound, undocumented status
enum values, float/int amount coercion, undocumented rate limit, a stale
materialised summary endpoint).

Dropped for three reasons:

1. **Fabricated.** The drifts were invented, so the fairness rationale rested on
   an assertion that they were "realistic" rather than on evidence.
2. **Black-box problem.** Hiding the server's source required either a compiled
   binary, a stripped wheel, or filesystem-permission tricks with a non-root
   agent — all fragile, and all of it load-bearing. If the agent could read the
   server source, `grep` solved the task in two minutes.
3. **Not connected to anything real.** The brief asks for a task with "some
   connection to reality"; a made-up vendor has none.

Replaced by a scenario built on `corespan/aistudio-server` (Apache-2.0, authored
by the submitter) — a real LLM-benchmarking and GPU-orchestration backend.

---

## 2026-11-02 — Key finding: the confounds already exist in the real code

Reading `app/routers/ingest.py` changed the design. The ingest path applies
silent defaults for every field that governs whether two benchmark results are
comparable:

```python
"pipeline_version": payload.config.get("pipeline_version", "unknown"),
"gpu_count":        payload.config.get("gpu_count", 1),
"precision":        payload.config.get("precision", "fp16"),
"input_tokens":     payload.config.get("input_tokens", 0),
"output_tokens":    payload.config.get("output_tokens", 0),
```

Consequences, all reachable without inventing anything:

- `parallelism` stays `NULL` when `metrics.parallelism` is absent, so a tp8 run
  and a tp4 run become indistinguishable in the leaderboard.
- `precision` silently becomes `fp16`, so an fp8 run is mislabelled and looks
  implausibly fast.
- `gpu_count` silently becomes `1`, so any per-GPU normalisation is wrong by 4-8x.
- `input_tokens` / `output_tokens` become `0`, leaving throughput unanchored.
- `duration_seconds` is `None` under node/server clock skew (the `delta > 0`
  guard), so a run can appear instantaneous.
- `on_conflict_do_update` keys on `(run_id, sub_run_index)`, so re-ingesting the
  same logical run under a *new* `run_id` duplicates silently.
- `status` is `.lower()`-ed with no enum check, so any string is accepted.

The migration history corroborates that this was a real, recurring problem:
`add_parallelism_to_benchmark_results`, `add_run_recipe_to_benchmark_results`,
`add_image_tag_to_workload_types`, `add_server_name_to_benchmark_results` were
each added separately. Those columns exist because results kept turning out not
to be comparable.

**Why this matters for fairness.** The task plants no tricks. Every confound is
the natural output of a defaulting code path that the agent is given and can
read. The economically viable deliverable is the validation layer that should
have existed.

**Why this matters architecturally.** It dissolves the black-box problem that
made the Meridian design fragile. The object of investigation is the *database*,
not the server source; and the agent legitimately needs the application source
because it has to patch it. The only things hidden are the held-out fixture and
the tests, which Harbor hides by construction. Plain compose, no permission
tricks, no compiled artefacts.

The trap survives the rewrite, and is now in real code rather than invented:
`total_token_throughput` is commented *"Primary leaderboard sort key."* The lazy
path — one tool call, `ORDER BY total_token_throughput DESC` — looks entirely
reasonable and is wrong.

---

## 2026-11-02 — Harbor toolchain findings

Facts established by reading the installed package rather than the docs, because
the published `harbor-task-creator` skill is out of date in several respects.

- Real schema is `schema_version = "1.4"`, not `version = "1.0"`.
- Network policy is `[environment] network_mode` with values `no-network` /
  `public` / `allowlist`. `allow_internet` still parses but is legacy.
- `[verifier] environment_mode` is `shared` | `separate`, defaulting to
  **separate** — the verifier gets its own `tests/Dockerfile`, so test
  dependencies belong there, not installed inside `test.sh` as the skill doc says.
- MCP transports are `stdio` | `sse` | `streamable-http`
  (`harbor/models/task/config.py:632`).
- Harbor resolves network policy per phase and auto-allowlists the inference
  endpoint host (`harbor/trial/network_policy.py`, `add_inference_hosts`).
  **Therefore `network_mode = "no-network"` is viable**: the task is fully
  hermetic while the agent harness can still reach the model API. No network
  nondeterminism anywhere in the task.
- Real CLI verbs are singular: `harbor task`, `harbor trial`, `harbor check`,
  `harbor lint`.
- `harbor init --include-canary-strings` stamps a canary GUID into task files —
  included deliberately as evidence against the "copied from an existing
  benchmark" concern.

### Local environment

macOS 12.6.5 is the root cause of a chain of problems: Apple's `vz` backend
needs macOS 13+, Homebrew no longer builds bottles for this configuration
(Tier 3), and Colima therefore requires QEMU built from source or installed via
MacPorts. Also: harbor cannot be installed under Python 3.15 — `litellm` pulls
`fastuuid`, whose PyO3 caps at 3.14 — so the tool environment is pinned to 3.13.

None of this affects the submitted task, which must build on vanilla Docker +
Compose on the grader's machine. Noted here only so the reproduction
instructions do not accidentally encode local workarounds.

---

## 2026-11-03 — Schema fidelity, and the join path that makes this long-horizon

Read the remaining models rather than guessing. The real `task_logs` has
`task_id` (UUID FK to `tasks.id`), `line` and `logged_at` -- not the
`run_id`/`stream`/`content` columns the first draft of the generator invented.
Corrected `schema.sql` to a faithful subset of five tables.

The real join path is the best thing to come out of this:

```
benchmark_results.run_id = tasks.run_name
tasks.id                 = task_logs.task_id
```

There is **no direct foreign key** from a result row to a log line. Connecting a
leaderboard number to the execution that produced it requires discovering that
`run_id` and `run_name` are the same identifier under two names. That is a real
piece of schema archaeology, and it is in the upstream code, not invented here.

`tasks.task_config` turns out to be the authoritative snapshot of what was
*requested*, as opposed to what `ingest.py` *stored*. Defects are therefore
provable by triangulating three tables rather than trusting one blob.

Difficulty lever added: roughly 30% of tasks carry an empty `task_config`
(realistic -- they predate the snapshot feature), including at least two
defective runs. A solution that only diffs requested-vs-recorded config will
provably miss those; they can only be reconstructed from the launch arguments
and declared sweep in `task_logs`.

## 2026-11-03 — Duplicate identity was ill-defined (fixed)

Both members of a duplicated pair were byte-identical apart from `run_id`, so
"which copy is the redundant one" had no answer derivable from the data, and the
`-retry` suffix made the whole class greppable in one command.

Fixed: a redelivered task now gets an ordinary fresh identifier, and fires 37
minutes later. "The redundant copy" is now well defined as the later-started
member of a pair sharing an identical metrics fingerprint. Identical throughput
to two decimal places across every sub-run is the tell -- real re-measurement
never reproduces exactly.

## 2026-11-03 — Solvability validated before building the container

Loaded `schema.sql` plus a generated corpus into PostgreSQL 16 and ran the
oracle's detection logic (`solution/detect.sql`) against ground truth, on three
independently seeded corpora:

```
seed 20261102: expected=16 detected=16 missed=0 fp=0  EXACT
seed 777001:   expected=16 detected=16 missed=0 fp=0  EXACT
seed 424242:   expected=16 detected=16 missed=0 fp=0  EXACT
```

Zero false positives means all three decoys survive: the genuine single-GPU run,
the correctly-recorded fp8 run, and the legitimately short sweep are not flagged.

**One fairness bug found by doing this, and fixed at the source.**
`missing_parallelism` had been injected into a single-GPU t4 run. On a 1-GPU
recipe a NULL `parallelism` has no comparability consequence -- `tp1` is the only
possibility -- so a validator would have been punished for *not* flagging a
harmless omission, while the single-GPU decoy rewards exactly that restraint. The
same observable would have been both defective and valid depending on which run
it appeared in, which is precisely the "hidden requirement" unfairness the brief
disqualifies. Injection is now restricted to multi-GPU recipes, so every instance
of the defect has a real consequence.

The fix went into the generator, not the detector. Making the detector match a
bad corpus would have hidden the ambiguity rather than removing it.

---

## 2026-11-03 — Architecture forced by the network policy

Intended design was compose with `main` + a `postgres` sidecar. Reading
`harbor/environments/docker/docker-compose-no-network.yaml` killed it:

```yaml
services:
  main:
    network_mode: none
```

`no-network` severs *all* networking for `main`, including to a sidecar. The
options were to weaken the network policy to `allowlist` (egress sidecar, keeps
inter-service DNS) or to remove the need for networking entirely.

Chose the latter: **a single container with PostgreSQL 16 inside it**, initialised
and seeded at image build time. Real Postgres, so JSONB / TEXT[] / enums / CHECK
constraints all behave exactly as upstream; no networking at any point; works
identically on every Harbor backend rather than only the compose one.

Build-time gotcha worth recording: the upstream `postgres` image declares
`/var/lib/postgresql/data` as a VOLUME, and writes to a declared volume during
build are discarded. `PGDATA` is therefore moved to `/var/lib/pgdata`, which is
not a volume, so the seeded cluster actually persists into the image.

The database is started by an `ENTRYPOINT` rather than `CMD`, so it comes up even
when the harness overrides the container command.

## 2026-11-03 — Verifier: standard library only

`network_mode = "no-network"` applies to the verifier phase too, so test
dependencies cannot be fetched at grading time. Rather than open a hole in the
network policy for pytest, the verifier uses **only the Python standard library**
and runs in `shared` mode. No pytest, no uvx, no index. Nothing about a grade can
depend on a mirror being up -- which is the same failure mode the brief
disqualifies, applied to the grader instead of the agent.

## 2026-11-03 — Oracle bug found by dry-running it

`build_records` selected `sub_run_index` but not `concurrency`, so every row came
back with `concurrency = None`, the sweep check failed universally, and the oracle
flagged all 53 runs and produced an empty leaderboard. Found by running the oracle
against a real database before building the container.

Worth noting the verifier would have caught this on its own -- the oracle would
have scored far below 1.0 -- which is the point of requiring the oracle to pass.

## 2026-11-03 — Scoring calibration against deliberately bad solutions

Five strategies run end-to-end (artifacts regenerated per strategy, not reused):

| Strategy | overall | func | constraint | robust | artifact |
|---|---|---|---|---|---|
| Oracle, all six classes | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Do nothing | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Flag everything | 0.030 | 0.074 | 0.000 | 0.000 | 0.000 |
| Memorise the seed run ids | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Partial: 3 of 6 classes | 0.770 | 0.720 | 0.700 | 1.000 | 0.720 |
| Column diff only, never reads logs | 0.770 | 0.933 | 0.333 | 1.000 | 0.968 |

The last row is the designed difficulty lever working. Diffing `task_config`
against the recorded columns, without ever reading `task_logs`, detects 93% of
defects and still produces a badly wrong leaderboard, because the defective runs
whose config snapshot is empty survive the audit and corrupt the rankings.

**A flaw in the first scoring design, found by this exercise.** `robustness` was
pure specificity, so a validator that flagged nothing scored a perfect 1.0 for
never having made a mistake -- 0.20 of the reward for doing nothing. Specificity
is now scaled by held-out recall (full credit from 50% recall upward), so
restraint only earns credit when there is something to be restrained about.

Degenerate strategies collapse to ~0, plausible-but-incomplete ones land near
0.77, and only a complete solution reaches 1.0. A pass bar of 0.85 sits in the
gap, so missing any single defect class fails -- without the grade sitting on a
knife edge.

---

## 2026-11-03 (evening) — MCP integration, branch `mcp-integration`

The real MCP server (`corespan/aistudio-server`, branch `feature/aistudio-mcp`,
pinned at `f4d9484`) now runs inside the task container. Three services on
loopback: PostgreSQL, the aistudio-server REST API, and `aistudio-mcp`.

`network_mode = "no-network"` survives this, because Docker's `none` network
still provides a loopback device. Harbor's Claude Code agent registers MCP
servers by writing `.claude.json` *inside* the container, so a `127.0.0.1` URL
is reachable while the task remains completely offline.

### Why the tool surface is a gift

`throughput_compare` compares a run "against comparable past runs" using the
*recorded* configuration -- precisely what this task corrupts. A run whose
precision was silently defaulted to fp16 gets compared against genuine fp16 runs
and reported as a large improvement. The lazy path is a real tool giving a
confident, well-formatted, wrong answer, and it is upstream code rather than
anything planted here.

Better still: `/api/v1/benchmarks` returns a derived `per_gpu_throughput_tok_s`.
The API therefore propagates `defaulted_gpu_count` straight into a headline
metric, 4-8x too high. That was not designed; it fell out of using the real code.

`get_task_logs` takes a workload id (`wl-...`), not a `run_id`, so reaching log
evidence requires traversing workload -> task -> run. The tool signature now
enforces the schema archaeology.

### Auth

Verification cannot be switched off: `verifier()` raises unless `MCP_JWKS_FILE`
or `MCP_JWKS_URL` is set. So a throwaway ES256 key, its JWKS, and a long-lived
admin token are generated at authoring time and committed
(`environment/gateway/`). The server runs with `MCP_JWT_MAX_LIFETIME_SECONDS=0`,
lifting mint.py's one-day cap, because a token that expired would make a rerun
fail for reasons having nothing to do with the agent. The key authenticates
nothing outside the sandbox: no network, and the only server it addresses lives
in the same container. Harbor forbids literal credentials in MCP headers, so the
header is `Bearer ${AISTUDIO_MCP_TOKEN}` with the value in `[environment.env]`.

### Integration problems found by testing, not assuming

Ran the real API in-process against the seeded database before building any
image. `/health` returned `{"status":"healthy","database":"ok"}`, but:

- `/api/v1/benchmarks` and `/api/v1/gpu-specs` failed with `UndefinedTableError`
  on **gpu_specs**, and `/api/v1/workload-types` on **workload_types**. The
  schema subset was missing two tables the real routes join against. Both added
  and populated; every endpoint the MCP tools use now returns 200.
- The two lock files pin conflicting shared versions (`anyio` 4.14.2 vs 4.15.1),
  so the image builds **two virtualenvs** rather than one. Both install with
  `--require-hashes`, so a swapped wheel fails the build.

### Known limitation, recorded deliberately

`summary` reports over a rolling `last_30d` window, so its output drifts with
wall-clock time: once real time moves past the seeded timestamps, it reports
fewer runs and eventually none. Nothing graded depends on it -- the verifier is
entirely time-independent -- but the agent's view of that one tool is not stable
across distant reruns. Shifting the corpus to build time would trade this for
non-determinism between builds, which is worse. Documented rather than hidden.

### Deliberately not done

`psql` stays available. Removing it would force MCP usage and strengthen the
novelty claim, but the list endpoint omits `parallelism` and the raw `metrics`
blob, so an MCP-only agent could not observe a NULL parallelism column directly.
Unsolvable is the one failure the brief disqualifies outright; a decorative
second access path is a much cheaper price.

---

## 2026-11-03 (late) — Docker finally up; first real Harbor trial

Docker Desktop 4.41.2 installed and running (daemon 28.1.1). The image builds
natively on arm64: 1.05 GB, both `--require-hashes` installs, the build-time
`initdb` and seed, in roughly four minutes.

Verified with `--network none`, which is what Harbor applies: PostgreSQL, the
REST API and `aistudio-mcp` all come up on loopback, the MCP server reports
**31 tools** with writes disabled, an unauthenticated call gets 401, and the
admin token completes an `initialize` handshake and opens a session.

One fix needed along the way: the DNS-rebinding guard rejected the call with
421 "Invalid Host header", because `MCP_ALLOWED_HOSTS` listed `127.0.0.1` but
callers send `127.0.0.1:8081`. The upstream code's own warning text says to list
the name with and without the port; it is now listed both ways.

### Two bugs the first trial found that local testing could not

**`ModuleNotFoundError: No module named 'psycopg2'`.** The oracle's `audit.py`
runs under the system interpreter, and the Dockerfile rewrite for the MCP work
dropped `python3-psycopg2`. Local validation never caught it because the local
runs used a `uv` environment that had the driver. Fixed by reinstating the apt
package.

**`/tests/test.sh: No such file or directory` in the verifier container.**
Reading `resolve_verifier_environment_definition` explained it: setting
`[verifier.environment].docker_image` marks the definition `bundled_tests=True`,
so Harbor skips uploading `tests/` and expects them to already exist in that
image — which a stock `python:3.12-slim` obviously does not.

The supported pattern is a `tests/Dockerfile` that bundles them itself, which is
exactly what `harbor init` scaffolds and which I deleted earlier when switching
to shared mode. Restored, with no package installs in it at all: the checker is
standard-library only, so the verifier image needs nothing but Python and a
`COPY . /tests/`.

Worth recording as a general lesson: both bugs were in the seams between
components, and neither was reachable by testing the components individually.
The first end-to-end run found both in fifty seconds.
