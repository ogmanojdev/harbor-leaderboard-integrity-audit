# What makes these tasks expensive

`RUN_REPORT.md` §8 closes on an open lead rather than a result: seven trials
consumed $3.19 of a $35 budget, so the tasks are roughly an order of magnitude
smaller than the budget implies, and the perfect scores are partly a fact about
their size. The remedy suggested there was a bigger, more realistic, more
layered task — one trial costing $3–10, meaning hundreds of tool calls.

This document reports the three experiments that tested that remedy and then
asked the sharper question behind it. Ten trials now stand at 1.000. Two things
were found to move cost, and exactly one of them is available to a fair task.

**Measured here**

1. **Cost tracks the number of distinct diagnoses, and nothing else.** Doubling
   the planted defects doubled cost. Tripling the source surface and tripling
   the number of independent verification surfaces moved it by nothing
   measurable (trials 7 → 8).
2. **Removing one specification ambiguity cut the same task's cost by 42% and
   its output tokens by 54%** (trials 9 → 10). The ambiguity, not the planning,
   was the expensive part.

The second is the only lever that changed cost per unit of work — and it is the
one the assignment forbids, since it disqualifies vague instructions and hidden
requirements by name. Everything the brief encourages was measured and did
nothing.

## Experiment 1: scale, realism and more gates (trials 7 → 8)

A new task, `collinear-candidate/release-back-to-green`, deliberately moved all
three variables the lead named, in the direction it recommended:

| | trial 7 (`pipeline-back-to-green`) | trial 8 (`release-back-to-green`) |
|---|---|---|
| defects | 4 | 8 |
| source surface | 4,605 LOC, 36 files | 15,256 LOC, 104 files |
| verification surfaces | 1 (`e2e.sh`) | 3 (suite, live path, migration chain) |
| failing signals | 1 stage | 39 test failures across 10 classes, plus 2 gates |

The same real application underneath — `corespan/aistudio-server`, Apache-2.0,
authored by the submitter — but vendored whole at `master` rather than as the
`app/` slice: the FastAPI service, the worker, its 9-revision Alembic chain, its
106-test pytest suite, its published API contract, and the MCP server.

The database is built by running the migration chain, not by hand-written DDL,
so the chain is load-bearing. The three gates were chosen to observe *different*
things, so that no single fix could clear them:

- **SUITE** builds its schema from the ORM models into a scratch database.
- **LIVE** runs ingest → leaderboard against the real database, which the
  migration chain built.
- **CHAIN** rebuilds a database from the revisions alone and diffs the result
  against the models.

That divergence is a real bug class, not a contrivance: a column mapped by the
ORM but never migrated is invisible to a suite that calls `create_all`, and
fatal to a service running on a chain-built database.

## Result

**1.000, again.** Eighth trial, eighth perfect score.

| | trial 7 | trial 8 | ratio |
|---|---|---|---|
| cost | $0.41 | $0.79 | 1.9× |
| tool calls | 15 | 30 | 2.0× |
| assistant turns | 29 | 54 | 1.9× |
| output tokens | 5,847 | 9,344 | 1.6× |
| input tokens | 569,815 | 1,402,642 | 2.5× |
| agent wall time | 2m 01s | 3m 45s | 1.9× |

## What the numbers say

Normalise by the three variables that were changed:

| | per defect | per 1,000 LOC | per gate |
|---|---|---|---|
| trial 7 | 3.75 calls, $0.103 | 3.26 calls | 15 calls |
| trial 8 | 3.75 calls, $0.099 | 1.97 calls | 10 calls |

Cost per defect is flat to within 4%. Calls per defect are **identical to two
decimal places**. Per-LOC and per-gate figures fell by 40% and 33%, which is
what it looks like when a variable is not driving the outcome.

> Cost tracks the number of distinct diagnoses the task requires. Tripling the
> source surface and tripling the number of independent verification surfaces
> contributed nothing measurable.

The mechanism is visible in the trajectory. The agent's first call was
`ls; cat gates.sh e2e.sh chain.sh; find app alembic -type f; ./gates.sh`. It
acquired the entire 15k-line layout and all three gate definitions in one call,
then worked the defects. More surface is read in the same call; more gates are
read in the same call. Only another defect costs another diagnosis.

### The authoring lever failed too

One defect, D10, was designed specifically to force code *authoring* rather than
patching: `build_llm_benchmark_command` was reverted to a plausible pre-release
revision, missing the node env prelude, the results bind-mount, the HF_TOKEN
passthrough, the `--tp` flag and the registry image. Its contract stayed
published in six tests and its own docstring. Restoring it is ~45 lines.

Output tokens rose from 5,847 to 9,344 — and **per defect they fell**, from
1,462 to 1,168. The model did not write a body. It read `config.py`, the
docstring, `docs/workloads.md` and the benchmark arguments across three calls,
then issued one targeted splice. It reconstructs minimally from precise reading
rather than authoring, so "make it write code" does not convert into output
tokens the way it would for a human.

This was a prediction made before the trial and falsified by it.

### Revised extrapolation

At $0.099 per defect and 3.75 calls per defect:

| target | defects required |
|---|---|
| $1 | ~10 |
| $3 | ~30 |
| $5 | ~50 |
| $10 | ~100 |

The budget inference in §8 was right that these tasks are ~10× smaller than
$35 implies. Its proposed remedy — scale, realism, layering — is refuted. The
only lever that moved was defect count, and it is linear, so reaching the
budget's implied size means roughly 30 to 100 planted defects in one task.

A 30-defect task is a scavenger hunt. It is *less* realistic than an 8-defect
one, not more, and it measures endurance at a repeated 3.75-call loop rather
than long-horizon reasoning. So the honest conclusion is not "build a bigger
one":

> This task family has a cost ceiling, and defect-count scaling only reaches
> the budget's implied horizon by abandoning the realism that justified the
> task in the first place. Horizon here is not a property of the system under
> test; it is a property of how many independent diagnoses the author plants.

What would actually raise cost is a task where step N+1's information does not
exist until step N has executed — the generalisation already recorded in §8 —
and crucially where each step's *diagnosis* is expensive, not merely each
step's fix. Eight trials have not produced one.

## Experiment 2: a task with nothing to patch (trials 9 → 10)

Ten trials say Opus wins by reading precisely, diagnosing locally and patching
surgically. So the third design removed the thing it is good at: there is no
defect to find and no code to repair.

`collinear-candidate/comparable-baseline-plan` asks for a **plan**. Every
benchmark run in the historical corpus must reach a floor of three comparable
peers other than itself, within a sweep budget. Three properties make it
different from everything above:

- **The rule is implemented, not stated.** What counts as a comparable peer, and
  what makes a past run usable as one, live in `comparable_results` in the MCP
  tool server and in the test that pins it. The instruction says to find and
  apply it, and does not describe it.
- **The provided validator is deliberately partial**, and says so in its own
  header: it checks structure, and explicitly not coverage, not eligibility, and
  not the budget. Passing it proves nothing.
- **The corpus exercises the eligibility clause.** Two realistic ineligibility
  patterns were added — an out-of-memory sub-run at the top of a sweep, and a
  runner that wrote its row before dying without metrics. Counting every row
  finds 48 configurations short; checking `status` alone finds 57; applying the
  full clause finds 67.

### Trial 9: it audited the specification

**1.000** — and the interesting part is what its notes contained. It found two
ambiguities in the task that the author had not seen:

- `app/routers/results.py::_build_filter_conditions` drops any filter whose
  value is unset or zero, so the 16 corpus rows with a zero token count match
  every token setting through the REST path. "Comparable" was therefore
  undefined for those configurations.
- `comparable_results` excludes the target's own run, so a floor of three peers
  *per run* requires four eligible runs per configuration, not three. The
  verifier counted three.

Both were checked against the source afterwards. Both held. It then computed
that 10 sweeps met the strict reading, and spent the remaining 4 of its budget
of 14 satisfying both readings at once — using the author's budget slack as
insurance against the author's imprecision.

That is not a model failure. On this task the model performed better
specification analysis than the person who wrote the specification.

### Trial 10: the same task, said precisely

The spec was then tightened: the floor stated per run and excluding itself, the
listing-endpoint disagreement declared with the peer-matching logic named as
authoritative, and the budget set to the true optimum of 23 sweeps, leaving no
slack to hedge with.

| | trial 9 (ambiguous) | trial 10 (precise) | change |
|---|---|---|---|
| result | 1.000 | 1.000 | — |
| cost | $0.834 | $0.483 | **−42%** |
| tool calls | 21 | 16 | −24% |
| output tokens | 17,128 | 7,914 | **−54%** |
| agent time | 3m 24s | 1m 41s | −50% |
| sweeps planned | 14 of 14 | 23 of 23 | optimal both times |

Same task, same corpus, same container, same grading structure. The only
variable was the precision of the requirement.

> Ambiguity resolution was 42% of that task's cost. Trial 9 produced the highest
> output-token count of any trial in this work — nearly three times trial 10's —
> and it was not spent authoring code. It was spent reasoning about what the
> requirement meant.

Trial 10's notes also show it proving minimality unprompted: *"23 sweeps, the
minimum possible, since each sweep adds only one run per concurrency level"*,
and noticing that planned runs must themselves clear the floor.

### What the two experiments add up to

Across ten trials, two levers moved cost:

| lever | effect | available to a fair task? |
|---|---|---|
| number of distinct diagnoses | linear, ~$0.10 and 3.75 calls each | yes, but reaching the budget's horizon needs 30–100 planted defects — a scavenger hunt |
| specification ambiguity | 42% of task cost in a controlled pair | **no** — the brief disqualifies vague instructions and hidden requirements |
| source surface (3.3×) | none measurable | yes |
| independent verification surfaces (3×) | none measurable | yes |
| forcing authored code over patches | none; output per unit *fell* | yes |

That table is the whole result. The things that make a task expensive for this
model are the things a fair task may not do, and the things the assignment
encourages — scale, realism, layering, more verification surfaces, real systems
over long sessions — were each measured and each did nothing.

It also explains the streak mechanically rather than as luck. Ten 1.000s are
not ten near-misses: they are what happens when every available lever is one
the model is indifferent to.

## Three defect classes falsified during calibration

Each was built, measured, and removed. The rejections are the reusable part.

**1. A defect must not break module import.** The first candidate pointed the
async DSN at an uninstalled driver (`postgresql+psycopg_async`). It broke
`app.database` at import, so pytest could not collect, and all three gates
reported the same `ModuleNotFoundError`. One `sed` cleared every gate at once.

This is worth stating plainly because *that defect was layer 1 of the shipped
trial-7 task*, where it was counted as the first of four layers. It is not a
layer. It is a bottleneck: it serialises everything behind one trivial fix and
makes a task look deep while making it cheap. It is part of why trial 7 cost
$0.41.

**2. A defect must be observable through a gate.** Removing the `RUNNING →
READY` edge from the workload state machine broke nothing any test or gate
watches. The agent could neither discover it nor verify a fix. That is a guess,
not a task.

**3. A defect must be exercised by the data.** Dropping the `.lower()`
normalisation from the model-config lookup was inert: every `model_id` in
`catalog.json` is already lowercase, so the call is a no-op and its removal is
unobservable. Presence in the code is not the same as presence in behaviour.

A corollary from mapping test coverage: the suite exercises `config`,
`manifest_builder`, `state_machine`, `catalog_seeder`, `schemas`, `catalog`, the
models and the routers, but not `nginx_proxy`, `ssh_executor`, `node_inspector`
or `sse.py`. Those four modules cannot host a fair defect, regardless of how
realistic a regression in them would be.

## A grading hole, found and closed

The graded probe originally ran `pytest tests/` — the agent's own copy. An agent
that weakened the suite would have scored for it. The instruction forbade
editing `tests/`, but the grader did not enforce it.

The image now keeps a pristine copy of the suite at `/opt/pristine-tests`, taken
before any defect is planted. The probe runs that copy and reports the SHA-256
of both it and `/app/tests`. The expected hash lives in `tests/check.py`, which
ships in the verifier image and is unreachable from the agent's container; any
mismatch zeroes all ten dimensions.

Verified in both directions:

- **honest** — both hashes match, pristine suite 106 passed, oracle 1.000.
- **cheat** — suite replaced with `def test_ok(): assert True`. The agent-facing
  `pytest tests/` reports `1 passed`; the probe still reports 67 passed / 39
  failed from the pristine copy, and the hash mismatch scores `overall 0.0`.

Trial 8 itself is unaffected: its trajectory only ever reads `tests/`, never
writes to it, and the run predates the fix only in ordering, not in outcome.

## Validation

- Oracle passes through Harbor at **1.000** on all ten scored dimensions.
- Baseline verified green before any defect was planted: `pytest` 106 passed,
  `e2e.sh` `PIPELINE GREEN`, chain single-head and round-tripping.
- All three gates independently red after planting, for three unrelated reasons.
- `harbor lint` clean on default rules. Under `--select ALL` it reports
  `unpinned-image` on both Dockerfiles and `root-agent`; the agent needs to
  manage PostgreSQL and write throughout `/app`, so it runs as root, as the
  submitted task does.
- Target model found all 8 defects, named each correctly in `fixes.md`, and went
  beyond them: it also masked IPs in detail sub-runs and normalised `model_name`
  and `precision`, having identified a `ck_gpu_type_lower` check constraint the
  task author had not accounted for.
- `comparable-baseline-plan`: oracle at 23 sweeps, **1.000** on all seven
  dimensions, `harbor lint` clean. Three deliberately wrong solvers fail three
  *different* dimensions — ignoring eligibility plans 20 sweeps and fails
  coverage; checking `status` alone plans exactly the oracle's 23 and still
  fails coverage; counting correctly but scheduling one sweep per configuration
  plans 174 and fails the budget. The verifier is diagnostic, not pass/fail.

## Limitations

- Two points define a line. The 3.75-calls-per-defect figure is consistent
  across trials 7 and 8 but rests on two measurements, at 4 and 8 defects. It
  may bend at 20 or 40; nothing here tests that.
- The 42% ambiguity figure is also a single pair. Trials 9 and 10 are a clean
  controlled comparison — same container, same corpus, same grading, one
  variable — but one comparison, at one task, with one ambiguity. It says that
  ambiguity was expensive here, not how expensive ambiguity is in general.
- Tightening the spec for trial 10 did two things at once: it removed the
  ambiguity *and* it disclosed the falsy-filter behaviour, which was the
  subtlest thing in the task. Part of the 42% is therefore a difficulty
  reduction rather than a pure ambiguity removal. The direction is not in doubt;
  the magnitude is an upper bound.
- Trial 9's spec defects were found by the model, not by the author's own
  review. Two deliberately wrong solvers and an oracle had all passed through
  that task before the model read it. That is a limitation of the calibration
  method used throughout this work: calibrators test the grader, not the
  wording.
- Both trials ran one attempt. Single-trial variance is unmeasured, so the
  1.9× cost ratio carries unknown error bars.
- The three variables moved together. The design isolates defect count only
  because the per-LOC and per-gate normalisations fell while per-defect stayed
  flat; it is not a factorial experiment.
- Both trials ran through OpenRouter rather than the first-party API, because
  that is what the assignment key provides. Harbor reported `cost_usd` for the
  top-level trial while the per-model entry read $0.00.
- `alembic check` is red on the pristine upstream repository (`gpu_specs` absent
  from `Base.metadata`, an uncreated composite index on `task_logs`, five
  drifted column comments). The CHAIN gate therefore tests structural
  round-trip and model/revision agreement rather than `alembic check`, so a
  baseline can be green.

## Reproduction

```bash
# Task: https://github.com/ogmanojdev/harbor-release-back-to-green (private,
# branch scale-up or master). The vendored application is omitted from this
# repository; `evidence/probes/release-back-to-green/` carries the design.
harbor run -c job.yaml -a claude-code -m anthropic/claude-opus-5.5 \
  --base-url https://openrouter.ai/api --job-name scale-trial-1 --yes
```

`harbor run` will not accept a task path: `-t/--task` parses as a package
reference (`org/name`) and there is no auto-discovery. The path has to arrive
through a JobConfig (`tasks: [{path: release-back-to-green}]`), and the agent
and model must stay on the command line — an `agent:` block in the YAML is
dropped from the resolved config.
