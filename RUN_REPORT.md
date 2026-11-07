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

Four trials were run against three task designs. Every one scored 1.000. The
designs are listed in the order they were built, because each was a response to
the previous result.

| # | design | hypothesis under test | result | runtime | cost |
|---|---|---|---|---|---|
| 1 | leaderboard-integrity-audit *(submitted)* | multi-source forensics with a published rule | **1.000** | 3m56s | $0.79 |
| 2 | backfill-exactly-once | volume + non-idempotent tool exhausts context | **1.000** | 1m40s | $0.28 |
| 3 | regression-in-twelve-runs @ 12 | irreducible sequential search under budget | **1.000** | 2m42s | $0.25 |
| 4 | regression-in-twelve-runs @ 10 | the same, with the budget tightened | **1.000** | 2m12s | $0.37 |

Logs, rewards and submitted artifacts for all four are under `evidence/`.

**Trial 1.** 32 turns, 14 tool calls, zero iteration, zero MCP calls. It read
`ingest.py`, ran five SQL queries, wrote one extraction script and the
validator, and stopped.

**Trial 2.** 10 tool calls. It invoked the backfill tool directly exactly
**once**, then wrote a driver that did the other 149 runs. Never processed a run
twice, never read the 159k tokens of archives — it wrote a program to read them.

**Trial 3.** Twelve of twelve runs, using six paired A/B comparisons that held
everything constant but the driver version. Recovered the exact three-clause
condition including the `tp >= 4` boundary rather than the tempting `tp = 8`.

**Trial 4.** The budget was cut to ten runs — the minimum the reference solution
needs. It **changed strategy**: one anchor pair to establish the effect size,
then seven single-variable ablations against that anchor instead of re-pairing,
plus one confirming pair on a second GPU. Exactly ten of ten, condition still
exact.

That last result is the most informative of the four, and it is worth stating
plainly: **the model's experimental design was better than the reference
solution's.** The oracle paid for a full ablation sweep; Opus recognised that an
anchored comparison costs half as much per hypothesis and switched to it when
the budget demanded.

### What three refuted hypotheses add up to

Each design targeted a documented weakness, and each failed for a reason worth
recording:

1. **No feedback loop** (trial 1). The task was a single-pass extraction, so
   nothing forced the agent to be wrong before being right.
2. **Context exhaustion** (trial 2). Volume only exhausts context if the *agent*
   must hold the content. Every remediation was mechanically derivable, so it
   wrote the rule once — 150 instances of a problem that needed solving once.
   Non-idempotency never bit either: a correct script does not repeat a step,
   and that trap only triggers on interrupted manual work.
3. **Sequential search under constraint** (trials 3 and 4). This one genuinely
   could not be scripted away — the information for each experiment did not
   exist until the previous one was paid for. Opus did the work, and did it
   well, at two different budget levels.

The generalisation that survives all three:

> A task resists one-shot solving only when the information required for step
> N+1 does not exist until step N has executed. Scale, layered flags and
> non-idempotency are each defeated by writing the rule once. Scale punishes
> humans; it does not punish programs.

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

Total spend across all four trials and the quality check: **$2.20 of $35**.

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
