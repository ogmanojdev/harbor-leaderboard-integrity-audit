# collinear-candidate/leaderboard-integrity-audit

**Submitted task:** [`leaderboard-integrity-audit/`](leaderboard-integrity-audit/) — an
agent audits a GPU benchmark leaderboard for runs that are invalid or not
comparable, publishes a corrected leaderboard, and patches the ingest validator
so the same defects cannot recur. Built on a real LLM-benchmarking backend I
designed and operate ([`corespan/aistudio-server`](https://github.com/corespan/aistudio-server),
Apache-2.0), vendored at a pinned commit.

```bash
harbor run -c job-leaderboard.yaml -a oracle --yes
harbor run -c job-leaderboard.yaml -a claude-code \
    -m anthropic/claude-opus-5.5 --base-url https://openrouter.ai/api --yes
harbor view jobs
```

Oracle passes at **1.000** on all five dimensions. `harbor lint` clean;
`harbor check` passes 11 of 11 rubric items.

**Second task:** [`sudoku-codec-frontier/`](sudoku-codec-frontier/) — an agent is
given a published 144-bit Sudoku compression scheme as working code and asked to
beat it, reaching a lossless, fixed-length, self-delimiting codec at 108 bits or
fewer on 10,000 held-out puzzles. It exists because all eight earlier designs
were defect-finding or plan-writing; this one is optimisation against a
verifiable objective, which allows a threshold placed just past where a
competent single pass lands. Oracle **1.000** at exactly 108 bits.
Write-up: [`SUDOKU_CODEC.md`](SUDOKU_CODEC.md).

## The headline, stated plainly

**No trial produced a failure.** Ten target-model trials across eight task
designs, every one scoring 1.000. That is the opposite of the assignment's
stated goal, and this repository argues the absence is a result rather than an
omission — because the eighth trial measured *why*:

> Cost tracks the number of distinct diagnoses a task requires, and nothing
> else. Doubling the defects doubled cost. Tripling the source surface
> (4,605 → 15,256 lines) and tripling the number of independent verification
> surfaces (1 → 3) moved it by nothing measurable.

Opus 5.5 wins these tasks by reading precisely, diagnosing locally, and patching
surgically — 3.75 tool calls per defect, invariant across both measured points.
Reaching the horizon the $35 credit budget implies would take 30 to 100 planted
defects in one task, which is a scavenger hunt rather than a long horizon.

A second measurement explains the streak. The only lever found to change cost
per unit of work was **specification ambiguity** — removing one from a task cut
its cost 42% and its output tokens 54% — and that is the one lever a fair task
is forbidden to pull, since the brief disqualifies vague instructions and hidden
requirements by name. Everything it encourages was measured and did nothing.

Five distinct failure mechanisms were predicted, built, and refuted on the way
there; three further defect classes died during calibration, one of which was a
layer of the submitted task. On the last design the model audited the task's own
specification and found two defects in it that the author had missed.

## Reading order

| document | what it covers |
|---|---|
| [`RUN_REPORT.md`](RUN_REPORT.md) | The submitted task in full: fairness rationale, economic realism, verifier design, shortcut-resistance analysis, calibration against deliberately bad solutions, all eight model runs, limitations, provenance. §8 is the model runs. |
| [`COST_SCALING.md`](COST_SCALING.md) | The eighth trial as a controlled experiment: the scaling measurement, the falsified prediction about forcing code authoring, three defect classes rejected during calibration, and a grading hole found and closed. |
| [`SUDOKU_CODEC.md`](SUDOKU_CODEC.md) | The ninth design, on a different axis: the measured 648 → 144 → 111 → 108 → 15.58-bit ladder, why the published corpus is unsafe to grade on unmodified, how the catalogue-lookup shortcut is closed by construction, nine calibrators, and the one integrity property that is weaker when the grader must execute the agent's code. |
| [`evidence/`](evidence/) | Every trial's logs, rewards, artifacts and trajectories. `evidence/probes/` holds the designs of the six probe tasks — none is a submission. |

## What is net-new

The task scenario, the defect taxonomy, the corpus, the verifier, the oracle and
every probe design were created for this exercise. The application underneath is
pre-existing open source of my own authorship, vendored unmodified at a pinned
commit and transformed into a task scenario it was never built for. Full
provenance and licence notes are in `RUN_REPORT.md` §10.

Nothing here is ported from SWE-bench, Terminal-Bench, a public CTF, a Kaggle
notebook, a public issue, or a prior Collinear task.
