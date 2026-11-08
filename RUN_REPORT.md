# Run report — collinear-candidate/leaderboard-integrity-audit

## 1. The task

A GPU benchmark leaderboard is about to be published, and hardware purchasing
decisions will be made from it. Several of the runs behind it are not valid or
not comparable with one another, and nobody knows which. The agent must find
them, publish a corrected leaderboard, and patch the ingest validator so the
same defects cannot recur.

Three artifacts are required:

| Artifact | What it is |
|---|---|
| `/app/audit/findings.json` | per-run defects, from a published code vocabulary |
| `/app/audit/leaderboard.json` | the corrected leaderboard, computed by a published rule |
| `/app/app/services/result_validator.py` | `validate_runs(records)`, exercised against a corpus the agent never sees |

## 2. Why the defects are real rather than planted

The task contains no invented corruption. Every defect is the natural output of a defaulting code path in the
real ingest endpoint, `app/routers/ingest.py`:

```python
"pipeline_version": payload.config.get("pipeline_version", "unknown"),
"gpu_count":        payload.config.get("gpu_count", 1),
"precision":        payload.config.get("precision", "fp16"),
"input_tokens":     payload.config.get("input_tokens", 0),
"output_tokens":    payload.config.get("output_tokens", 0),
```

Every one of those fields decides whether two benchmark results can be compared.
When a runner omits one, the default is recorded silently and the row looks
healthy afterwards:

- `parallelism` stays `NULL` when `metrics.parallelism` is absent, so a tp8 run
  and a tp4 run become indistinguishable.
- `precision` silently becomes `fp16`, so an fp8 run is mislabelled and looks
  implausibly fast.
- `gpu_count` silently becomes `1`, so per-GPU normalisation is wrong by 4-8x.
- `input_tokens` / `output_tokens` become `0`, leaving throughput unanchored.
- `on_conflict_do_update` keys on `(run_id, sub_run_index)`, so re-ingesting one
  logical run under a *new* `run_id` duplicates silently.

The upstream migration history corroborates that this was a recurring, real
problem: `add_parallelism_to_benchmark_results`, `add_run_recipe_to_benchmark_results`,
`add_server_name_to_benchmark_results` and `add_image_tag_to_workload_types` were
each added separately. Those columns exist because results kept turning out not
to be comparable.

**Economic viability.** Benchmark numbers drive hardware purchasing, capacity
planning and vendor selection. A leaderboard that silently compares an fp8 run
against fp16 runs, or divides an 8-GPU result by one, recommends the wrong
hardware at six or seven figures. The deliverable is the validation layer that
should have existed. Any team running an internal benchmark leaderboard has
this problem; most discover it the way the upstream migrations suggest it was
discovered here, one column at a time, after the fact.

## 3. The trap

`total_token_throughput` carries this comment upstream:

> Total tokens/sec across all concurrent requests. Primary leaderboard sort key.

So the obvious move — sort by it — is wrong, and the platform's own MCP tools
make the wrong move easy and comfortable:

- `throughput_compare` compares a run "against comparable past runs" using the
  **recorded** configuration, which is exactly what is corrupt. A run whose
  precision was defaulted to fp16 is compared against genuine fp16 runs and
  reported as a large improvement.
- `/api/v1/benchmarks` returns a derived `per_gpu_throughput_tok_s`, so the API
  propagates `defaulted_gpu_count` straight into a headline metric.
- `summary` reports dashboard totals over everything, defective runs included.

None of this was planted. It is what the real tools do with corrupt data.

## 4. Long-horizon structure

The task cannot be done in one step or from one file.

1. **Schema archaeology.** No foreign key connects a result row to a log line.
   `benchmark_results.run_id` equals `tasks.run_name`, and `tasks.id` equals
   `task_logs.task_id`. The MCP tool signature enforces this too: `get_task_logs`
   takes a workload id, not a `run_id`.
2. **Establish ground truth.** `tasks.task_config` records what was *requested*,
   as against what ingest *stored*. It is empty for roughly 30% of runs, which
   predate the snapshot feature, so intent must then be recovered from the
   launch arguments and declared sweep in `task_logs`.
3. **Enumerate six defect classes**, two of which are invisible per-row:
   a truncated sweep is a *count* against a declaration, and a duplicate is a
   cross-run fingerprint match.
4. **Avoid over-rejecting.** Three decoys trip naive heuristics while being
   genuinely valid.
5. **Recompute the leaderboard** under a published rule, excluding what failed.
6. **Generalise.** The validator is scored on a larger corpus the agent never
   sees, so nothing memorised survives.

## 5. Verifier design

Four independently scored dimensions in `reward.json`:

| Dimension | Weight | What it measures |
|---|---|---|
| `functional_correctness` | 0.35 | submitted validator on 65 unseen runs, macro-F1 over defect classes |
| `constraint_satisfaction` | 0.25 | corrected leaderboard, compared exactly |
| `robustness` | 0.15 | specificity on healthy runs, scaled by recall, times a determinism check |
| `artifact_quality` | 0.10 | findings over the local corpus, macro-F1 |
| `completeness` | 0.15 | every defect class reported at least once **and** an exact leaderboard |

Two of those deserve explanation, because both exist to close holes that
measurement exposed rather than reasoning.

**Macro-averaging, not micro.** Each defect class covers only two or three of
sixteen runs, so averaging over `(run, defect)` pairs let an entire class be
missed for roughly a tenth of the score. Averaging over classes makes missing
one cost a sixth of the dimension, which is what the instruction actually asks
for. Reporting a class that does not occur scores zero for that class, so
inventing defects is not free.

**A completeness dimension.** Even with macro-averaging, partial credit across
four dimensions left a submission that missed a whole class scoring near 0.9.
An audit that overlooks an entire category of integrity problem has not done the
job, however many individual runs it got right, so one dimension says so as a
yes-or-no.

Design choices worth stating:

- **Standard library only.** The task is offline in both phases, so grading
  cannot depend on fetching a test dependency. No pytest, no `uvx`, no index.
  Nothing about a grade can turn on whether a mirror is up — the same failure
  mode the brief disqualifies, applied to the grader instead of the agent.
- **Separate verifier container.** The three declared artifacts are collected
  from the agent's container and uploaded into a fresh one, so a submission
  cannot tamper with grading.
- **Graded on typed data, never prose.** `evidence` strings are explicitly not
  scored. The defect vocabulary is published in `instruction.md`, so comparing
  codes is a documented enum rather than brittle string matching.
- **A vocabulary wider than the corpus.** Nine codes are published; six occur.
  Publishing exactly the six present would hand over the enumeration, which is
  half the task. The extra three also probe whether a model asserts defects it
  has not evidenced.
- **The reward file is written on every path**, including from the checker's own
  exception handler.

## 6. Calibration against deliberately bad solutions

Each strategy run end to end, artifacts regenerated per strategy.

| Strategy | overall | verdict |
|---|---|---|
| Oracle, all six classes | 1.000 | pass |
| Reads logs only, ignores the config snapshot | 0.932 | pass |
| Reads the config snapshot only, ignores logs | 0.973 | pass |
| Misses `truncated_sweep` | 0.775 | fail |
| Misses `defaulted_gpu_count` | 0.762 | fail |
| Misses `zero_token_config` | 0.750 | fail |
| Misses `missing_parallelism` | 0.739 | fail |
| Misses `defaulted_precision` | 0.739 | fail |
| Misses `duplicate_logical_run` | 0.719 | fail |
| Reasons only from the recorded numbers | 0.334 | fail |
| Memorises the seed run ids | 0.000 | fail |
| Flags everything | 0.030 | fail |
| Does nothing | 0.000 | fail |

Pass bar 0.85. **Missing any single defect class fails.** A solution that works
from one evidence source still passes if it finds every class and publishes an
exact leaderboard, which is the correct outcome: that is a complete audit done
efficiently, not a shortcut.

### The task rewards thoroughness, not trap-avoidance

Worth stating plainly, because an earlier draft of this report overstated it.
This task is not a trick. A systematic agent that reads the logs for every run,
cross-references the configuration snapshot, and checks for duplicates across
runs will pass, and should. The difficulty is the volume and linkage of the
work: six classes across three tables with no foreign keys between them, two
defects invisible in any single row, three decoys, an exact aggregation rule,
and a validator that has to generalise.

The failure being probed is therefore incompleteness, not deception.

## 7. Fairness audit

| Requirement | How it is met |
|---|---|
| Solvable | Oracle passes. Detection reproduced exactly on three independently seeded corpora: 16/16, no false positives. |
| Unambiguous | `instruction.md` publishes the defect vocabulary, the exact leaderboard rule, the validator signature and input schema, and every output path. |
| Substantive | Failure comes from incomplete inspection, missed enumeration and trusting a summary tool — not from tricks or formatting. |
| Reproducible | No network in either phase. Database seeded at image build. Dependencies installed with `--require-hashes`. Corpus committed. |
| Non-brittle | Grading compares typed values and numbers. No exact-string matching anywhere. |
| Not time-limited | Agent budget is 5400s, roughly 3x the oracle path. |
| No leaked solution | `tests/` and `solution/` are never copied into the image; the generator lives outside every image. |

### Two fairness bugs found during development, and fixed at the source

**A defect that was not one.** `missing_parallelism` was initially injected into
a single-GPU run. On a 1-GPU recipe a NULL `parallelism` has no comparability
consequence — `tp1` is the only possibility — so a correct validator would have
been punished for *not* flagging a harmless omission, while the single-GPU decoy
rewards exactly that restraint. The same observable would have been both
defective and valid depending on where it appeared. Injection is now restricted
to multi-GPU recipes.

**An ill-defined duplicate.** Both members of a duplicated pair were identical
apart from `run_id`, so "which copy is redundant" had no data-derivable answer,
and a `-retry` suffix made the class findable with one `grep`. Redeliveries now
get ordinary fresh identifiers and fire 37 minutes later, so the redundant copy
is well defined as the later-started member of a fingerprint-matched pair.

Both fixes went into the generator, not the detector. Changing the detector to
match a bad corpus would have hidden the ambiguity rather than removed it.

### A scoring flaw found by calibration

`robustness` was originally pure specificity, so a validator that flagged
nothing scored a perfect 1.0 for never having made a mistake — 0.20 of the
reward for doing nothing. Specificity is now scaled by held-out recall, so
restraint earns credit only when there is something to be restrained about.

### Were the two evidence sources actually both necessary?

An earlier version of this task claimed that an empty `task_config` on ~30% of
runs forced the agent to read `task_logs`. Measurement showed the claim was
backwards: the logs carried the launch arguments, the GPU count, the declared
sweep and every result line, so they were a strict **superset** of the config
snapshot. A solver that simply always read the logs scored a perfect 1.000, and
the difficulty lever defended against nothing — least of all against the
behaviour a working engineer defaults to, which is to go and read the logs.

The corpus now withholds something from each source. Some tasks predate the
configuration snapshot and store an empty one. Others had their log capture drop
mid-task, so the recipe, declared sweep and launch line were never written —
realistic in a system that streams node output over SSE, and visible rather than
silent, because the reconnect marker survives. No run is missing both: that
would be unprovable.

| Evidence available to the solver | detection | leaderboard | overall |
|---|---|---|---|
| config snapshot + logs | 1.000 | 1.000 | 1.000 |
| logs only | 0.850 | 1.000 | 0.932 |
| config snapshot only | 0.933 | 1.000 | 0.973 |

Both single-source strategies now lose detection accuracy. Both still pass,
which is the right answer: each finds every defect class and publishes an exact
leaderboard. Reconciling the two sources is what recovers the last few runs.

Two further holes closed by the same exercise:

- **Nothing marks a truncated sweep any more.** The generator previously logged
  `ERROR: ssh channel closed unexpectedly`, so one `grep` found every instance.
  A worker killed mid-run writes no farewell; truncation now has to be found by
  counting recorded results against the declared sweep. The trailing
  `sweep complete` line was removed for the same reason — its *absence* was just
  as greppable.
- **An undetected duplicate now changes the answer.** Each leaderboard entry
  carries `runs_counted`, so a redelivered run that was not excluded inflates it
  and the entry is wrong. Previously a duplicate shared its original's metrics,
  so `max()` returned the same figure and missing the defect cost nothing in the
  deliverable.

The eligibility rule was also amended: a run now qualifies only if it recorded a
result at every concurrency it declared, and its peak is its highest recorded
throughput. The declared sweep is therefore load-bearing for the leaderboard
itself, not only for the audit.

### Can the task be shortcut by reasoning about the numbers?

A frontier model carries priors about inference throughput, and the corpus also
permits outlier analysis within itself. Either could in principle substitute for
reading the evidence. This was measured rather than argued.

A validator was built that uses **only** the recorded metrics in
`benchmark_results` -- no `task_config`, no `task_logs`, no joins -- flagging
runs whose per-GPU throughput deviates from the median of its
`(model_name, gpu_type)` peers. It was then scored end to end:

| | numbers only | oracle |
|---|---|---|
| defective runs identified | 4 of 16 | 16 of 16 |
| held-out F1 | 0.316 | 1.000 |
| leaderboard | 17 entries, 13 spurious | 9, exact |
| **overall** | **0.334** | **1.000** |

That figure is a *generous* upper bound: the numbers-only solver was handed the
leaderboard aggregation rule for free, which it could not otherwise have had.

Which classes are numerically visible:

| Defect class | Caught by numbers alone |
|---|---|
| `defaulted_gpu_count` | 3 of 3 |
| `truncated_sweep` | 1 of 3 (incidental -- a truncated run has a low peak) |
| `defaulted_precision` | 0 of 3 |
| `missing_parallelism` | 0 of 3 |
| `duplicate_logical_run` | 0 of 2 |
| `zero_token_config` | 0 of 2 |

Only `defaulted_gpu_count` has a real numeric signature, and it does not depend
on training data at all: a row recording one GPU while reporting eight GPUs'
throughput is arithmetically impossible. Any competent analyst sees it. That is
one class of six, and it is a legitimate way to form the hypothesis.

`defaulted_precision` turns out **not** to be numerically detectable here, which
was not predicted. The fp8 recipes also use a different token configuration
(2048/512 against 1024/1024), so their throughput is not comparable to the bf16
runs by raw numbers; "suspiciously fast for fp16" cannot be separated from
"different workload shape" without reading the configuration or the launch line.
The remaining four classes are structural facts with no numeric signature at all.

There is also a structural reason the shortcut cannot close: the published
leaderboard rule requires each run's **declared concurrency sweep**, which exists
only in `task_config` or `task_logs`. No amount of numeric reasoning produces the
required deliverable without performing the joins.

**The fairness result matters more than the difficulty result.** The numbers-only
analysis produced **zero false positives** -- it never wrongly condemned a valid
run. The risk worth worrying about was the reverse of the one asked about: that
synthetic throughput figures would look implausible to a model with real-world
priors, causing it to flag healthy runs and fail for a reason that is not its
fault. That does not happen here. The two decoys most likely to attract suspicion
-- the genuinely fp8 run and the genuine single-GPU run -- both carry evidence
that exonerates them, so noticing "this looks fast" and then checking is exactly
the behaviour they reward.

### Independent quality check

`harbor check` runs an LLM evaluator against an 11-point rubric. All eleven
pass: behaviour covered by the instruction, behaviour covered by tests,
informative test structure, anti-cheating measures, structured data schema,
pinned dependencies, no typos, no tests or solution in the image, no test
dependencies in the image, no hardcoded solution, and output paths stated.

It also found three defects worth recording, all since fixed:

- **A leak in the corpus.** Each decoy run carried a `"decoy"` label in its
  metrics blob, marking it as safe. It revealed no defective run, but it
  disarmed the very false-positive test the decoys exist to run. Removed; the
  notes now live only in the ground-truth manifest, which the verifier sees and
  the agent does not.
- A stale module docstring in the checker still described four dimensions at the
  old weights after the fifth was added.
- `test.sh`'s fallback reward omitted the `completeness` key.

The first is the one that mattered, and it is a good argument for running the
check: it is exactly the kind of thing that survives self-review, because the
author knows which runs are decoys and stops seeing the label.

## 8. Model runs

### Oracle

`harbor run -p ./leaderboard-integrity-audit -a oracle` — **1.000** on all five
dimensions, 0 exceptions, 40s. Reproduced across every revision of the task.

### Target model: Claude Opus 5.5, Claude Code harness

Seven trials were run against six task designs, and an eighth against a
seventh design after this section was first written (see
[COST_SCALING.md](COST_SCALING.md)). Every one scored 1.000. The designs are
listed in the order they were built, because each was a response to the
previous result.

| # | design | hypothesis under test | result | runtime | cost |
|---|---|---|---|---|---|
| 1 | leaderboard-integrity-audit *(submitted)* | multi-source forensics with a published rule | **1.000** | 3m56s | $0.87 |
| 2 | backfill-exactly-once | volume + non-idempotent tool exhausts context | **1.000** | 1m40s | $0.24 |
| 3 | regression-in-twelve-runs @ 12 | irreducible sequential search under budget | **1.000** | 2m42s | $0.36 |
| 4 | regression-in-twelve-runs @ 10 | the same, budget cut to the oracle's minimum | **1.000** | 2m12s | $0.26 |
| 5 | audit-what-you-can-prove | epistemic overclaiming (an Opus 5.5 system-card regression) | **1.000** | 2m45s | $0.89 |
| 6 | two-regressions | the blind spot in the model's *own* observed method | **1.000** | 1m27s | $0.16 |
| 7 | pipeline-back-to-green | layered defects in a real service, run-diagnose-fix loop | **1.000** | 2m38s | $0.41 |
| 8 | release-back-to-green | scale, realism and more gates raise the horizon | **1.000** | 4m32s | $0.79 |

Logs, rewards and submitted artifacts for all eight are under `evidence/`.
Every cost above is the `cost_usd` recorded in that trial's `result.json`;
runtimes are whole-trial wall clock, which is why they exceed agent execution
time by the environment build and verifier.

**Trials 1-4** are described below. The last three are the most informative.

**Trial 5 — calibration.** Nine runs in the corpus have neither a config
snapshot nor usable logs, so their status cannot be established; four of the
nine are in fact defective. The deliverable required a list of runs the agent
could *not* rule on. It abstained on exactly those nine, overclaimed on zero,
and still reported all twelve provable defects. It did not even report
`zero_token_config` on a starved run, though that is visible in the columns —
it reasoned that a run whose declared configuration is unavailable belongs in
one list only. This design targeted a behaviour Anthropic's own system card
records as having *risen* in Opus 5.5. It did not reproduce under direct
measurement.

**Trial 6 — the model's own blind spot.** Trial 4 revealed its method: one
anchor, then single-variable ablations. That method provably misses a second,
independent cause, because ablating from one anchor characterises only the
cause active there. So the system was given two disjoint regressions. It spent
eleven runs on the first region, then at run twelve pivoted to the second and
isolated it independently — 128 of 128 affected configurations, exactly, using
all sixteen runs.

**Trial 7 — a real service that does not work.** Four layered defects in the
vendored FastAPI application: an uninstalled DB driver in the DSN, a column
missing from the database, an upsert against a non-existent constraint, and a
stale filter hiding every newly ingested row. Each is invisible until the one
before it is fixed. This is the only trial with a genuine loop — six
invocations of the end-to-end check, fixing one layer at a time.

It also produced the single most interesting artifact of the seven. On the
fourth defect the oracle deletes the offending filter; Opus instead fixed the
*ingest* side, and justified the choice by citing how two other modules in the
codebase handle the same field:

> Ingest now falls back to `payload.node_ip`, the same fallback NodeInspector
> and worker.py use.

It also backfilled the missing column from the metrics JSONB rather than
leaving it null, and flagged a fifth latent defect it had noticed but was not
asked about.

### What five refuted hypotheses add up to

Seven trials, five distinct mechanisms, every one scoring 1.000:

1. **No feedback loop** (trial 1). A single-pass extraction; nothing forced the
   agent to be wrong before being right.
2. **Context exhaustion** (trial 2). Volume only exhausts context if the *agent*
   holds the content. It wrote a program to read the archives instead.
3. **Sequential search under constraint** (trials 3-4). Genuinely unscriptable,
   and it did the work — then re-planned to a cheaper experimental design when
   the budget shrank, landing exactly on budget twice.
4. **Epistemic overclaiming** (trial 5). Targeted a documented regression in
   this model. Perfect calibration; zero overclaims.
5. **A blind spot in its own method** (trial 6). Derived from observed
   behaviour rather than hypothesis. It pivoted regions unprompted.

And one task-shape change (trial 7): a real service that does not work, which
produced the only genuine diagnose-fix-rerun loop of the seven — and a fix
better than the reference solution's.

The generalisation that survived all of it:

> A task resists one-shot solving only when the information required for step
> N+1 does not exist until step N has executed. Scale, layered flags and
> non-idempotency are each defeated by writing the rule once. Scale punishes
> humans; it does not punish programs.

### What the budget was telling us

Collinear provisioned $35 of isolated credits. Seven trials consumed **$3.19**,
the most expensive being $0.89. If that budget was sized for a long-horizon
task, a single trial was expected to cost several dollars — so these tasks are
roughly an order of magnitude smaller than the brief had in mind, and the
perfect scores are partly a fact about their size rather than only about the
model.

Cost is a reasonable proxy for horizon, because it is tool calls times context.
The benchmarks where Opus 5.5 does fail are expensive ones: Terminal-Bench 4.0
sits at 66.4%, and those tasks involve real systems over long sessions. Trial 7
moved in that direction — the only trial with a real diagnose-fix loop — but at
$0.41 it was not even the most expensive of the seven, which sharpens the point
rather than softening it: the one task that forced a genuine loop was mid-range
in cost, and far short of what the budget implies.

That is the clearest open lead from this work, and it is recorded here rather
than claimed as a result.

**Trial 8 closed it, and the remedy proposed above is wrong.** A second task was
built to move all three variables at once — defects 4 → 8, source surface 4,605
→ 15,256 lines, verification surfaces 1 → 3 — and measured. It scored 1.000 for
$0.79. Cost per defect was flat ($0.103 → $0.099) and calls per defect were
identical at 3.75, while per-LOC and per-gate cost fell by 40% and 33%: cost
tracks the number of distinct diagnoses, and neither scale nor realism nor
layering moved it. Reaching the budget's implied size therefore needs 30 to 100
planted defects in one task, which is a scavenger hunt rather than a long
horizon. Full method, the three defect classes falsified during calibration, and
a grading hole found and closed: **[COST_SCALING.md](COST_SCALING.md)**.

### The method error, stated once

Difficulty on the submitted task was calibrated against deliberately weak
solvers — do-nothing, memorise-the-ids, miss-a-defect-class. Those numbers were
precise and said nothing about a strong solver. The cheap move not taken was
trialling the real target on day one, for under a dollar, before investing in
verifier quality and documentation. Every later design was built loop-first and
trialled immediately, which is why trials 2, 3 and 4 cost two days between them
rather than five.

### Why no failure is reported

No trial produced one. The budget could have been cut to nine runs, below what
the reference solution needs, and trial 4 would have failed — but that failure
would measure the margin chosen rather than the model's planning, which is the
kind of result the brief disqualifies. Two refusals are recorded here instead of
a manufactured failure: that one, and forcing MCP-only access on the submitted
task, which would have made six defective runs unprovable.

Total spend across all eight trials: **$3.98 of $35**, each figure taken from
the `cost_usd` in `evidence/trial-*/result.json`. The `harbor check` run is not
included — its cost was not recorded in the evidence kept here.

## 9. Limitations, stated plainly

- **`summary` drifts with wall-clock time.** It reports over a rolling
  `last_30d` window, so once real time moves past the seeded timestamps it
  returns fewer runs and eventually none. Nothing graded depends on it — the
  verifier is entirely time-independent — but the agent's view of that one tool
  is not stable across distant reruns. Shifting the corpus to build time would
  trade this for non-determinism between builds, which is worse.
- **`psql` remains available**, so an agent can bypass the MCP tools. Removing
  it would strengthen the MCP framing, but the list endpoint omits `parallelism`
  and the raw `metrics` blob, so an MCP-only agent could not observe a NULL
  `parallelism` column. Unsolvable is a worse failure than a redundant access
  path.
- **Metrics are synthetic.** Throughput figures come from a saturation curve,
  not from real hardware. Their absolute values carry no information; only the
  comparisons between them matter, and those are what the task turns on.
- **The signing key is committed.** It authenticates nothing outside the
  sandbox — there is no network, and the only server it addresses runs in the
  same container — and committing it is what makes the build reproducible.
- **One residual anti-cheat gap.** The verifier imports and executes the agent's
  own module, which is unavoidable for a patch-this-function task. It runs in a
  separate container, under a timeout, with the reward written on every path.

## 10. Provenance and licences

Created for this exercise. Not a port of SWE-bench, Terminal-Bench, a public
CTF, a Kaggle notebook, a public issue or a prior Collinear task.
`harbor init --include-canary-strings` stamped a canary GUID into the task files.

**New here:** the scenario, the corpus and its generator, the defect taxonomy,
the decoys, the verifier, the oracle, and all documentation.

**Vendored:** application source, database schema and MCP tool server from
[corespan/aistudio-server](https://github.com/corespan/aistudio-server),
Apache-2.0, authored by this submission's author, pinned at the commit in
`environment/VENDORED_COMMIT`. `LICENSE` and `NOTICE` ship alongside the code,
and `mcp-server/THIRD-PARTY-NOTICES.md` is retained.

No real benchmark data is used. Every run in the corpus is synthetic, and no IP
address, hostname or node identifier refers to real infrastructure.

## 11. Reproduction

```bash
# Harbor resolves the MCP header's ${AISTUDIO_MCP_TOKEN} from the shell before
# launching, so export it from the file that ships in this repository. The
# oracle does not use the MCP server and runs without it.
export AISTUDIO_MCP_TOKEN="$(cat leaderboard-integrity-audit/environment/gateway/agent-token.jwt)"

harbor run -p ./leaderboard-integrity-audit -a oracle
harbor run -p ./leaderboard-integrity-audit -a claude-code -m opus-5-5
harbor view ./jobs
```

Static checks:

```bash
harbor lint  ./leaderboard-integrity-audit
harbor check ./leaderboard-integrity-audit
```

Regenerating the corpus (changes committed fixtures; both corpora must be
regenerated together):

```bash
python3 tools/gen_runs.py --seed 20261102 --runs 48 \
  --out-sql environment/seed/seed.sql \
  --out-truth tests/fixtures/seed_truth.json \
  --out-records tests/fixtures/seed_records.json

python3 tools/gen_runs.py --seed 777001 --runs 60 \
  --out-sql /dev/null \
  --out-truth tests/fixtures/heldout_truth.json \
  --out-records tests/fixtures/heldout_records.json
```
