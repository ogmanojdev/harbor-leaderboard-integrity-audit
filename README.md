# collinear-candidate/leaderboard-integrity-audit

**Submitted task:** [`leaderboard-integrity-audit/`](leaderboard-integrity-audit/) — an
agent audits a GPU benchmark leaderboard for runs that are invalid or not
comparable, publishes a corrected leaderboard, and patches the ingest validator
so the same defects cannot recur. Built on a real LLM-benchmarking backend I
designed and operate ([`corespan/aistudio-server`](https://github.com/corespan/aistudio-server),
Apache-2.0), vendored at a pinned commit.

```bash
harbor run -p ./leaderboard-integrity-audit -a oracle
harbor run -p ./leaderboard-integrity-audit -a claude -m opus-5-5
harbor view ./jobs
```

Oracle passes at **1.000** on all five dimensions. `harbor lint` clean;
`harbor check` passes 11 of 11 rubric items.

## The headline, stated plainly

**No trial produced a failure.** Eight target-model trials across seven task
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

Five distinct failure mechanisms were predicted, built, and refuted on the way
there; three further defect classes died during calibration, one of which was a
layer of the submitted task.

## Reading order

| document | what it covers |
|---|---|
| [`RUN_REPORT.md`](RUN_REPORT.md) | The submitted task in full: fairness rationale, economic realism, verifier design, shortcut-resistance analysis, calibration against deliberately bad solutions, all eight model runs, limitations, provenance. §8 is the model runs. |
| [`COST_SCALING.md`](COST_SCALING.md) | The eighth trial as a controlled experiment: the scaling measurement, the falsified prediction about forcing code authoring, three defect classes rejected during calibration, and a grading hole found and closed. |
| [`evidence/`](evidence/) | Every trial's logs, rewards, artifacts and trajectories. `evidence/probes/` holds the designs of the six probe tasks — none is a submission. |

## What is net-new

The task scenario, the defect taxonomy, the corpus, the verifier, the oracle and
every probe design were created for this exercise. The application underneath is
pre-existing open source of my own authorship, vendored unmodified at a pinned
commit and transformed into a task scenario it was never built for. Full
provenance and licence notes are in `RUN_REPORT.md` §10.

Nothing here is ported from SWE-bench, Terminal-Bench, a public CTF, a Kaggle
notebook, a public issue, or a prior Collinear task.
