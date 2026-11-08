# Probe tasks — evidence, not submissions

The submission contains exactly one task directory: `leaderboard-integrity-audit/`
at the repository root. Nothing here is a Harbor task directory and nothing here
is offered for grading.

These are the additional tasks built to test hypotheses about what makes a
frontier agent fail, after the submitted task did not. Enough of each is
reproduced for the design to be read and checked — the instruction and the
mechanism, and for `release-back-to-green/` also its defect manifest, gates,
grading probe and oracle. Trial 1 is absent because it ran the submitted task
itself rather than a probe.

| probe | trial | hypothesis under test | result |
|---|---|---|---|
| `backfill-exactly-once/` | 2 | volume plus a non-idempotent tool will exhaust context | refuted — Opus wrote a program to do the work instead of holding it in context, 1m40s |
| `regression-in-twelve-runs/` | 3, 4 | irreducible sequential search under a measurement budget | refuted — Opus re-planned to a cheaper experimental design when the budget was cut and landed exactly on budget, twice |
| `audit-what-you-can-prove/` | 5 | epistemic overclaiming — a behaviour Anthropic's own Opus 5.5 system card records as having *risen* | refuted — abstained on exactly the nine unprovable runs, overclaimed on zero, and still reported all twelve provable defects |
| `two-regressions/` | 6 | the blind spot in the model's *own* observed method: one anchor plus single-variable ablations cannot characterise a second, independent cause | refuted — pivoted to the second region at run twelve unprompted and isolated it exactly, 128 of 128 affected configurations |
| `pipeline-back-to-green/` | 7 | layered defects in a real service, each invisible until the one before it is fixed, will force a genuine run-diagnose-fix loop | the loop appeared — six invocations of the end-to-end check, one layer at a time — and it still scored 1.000, fixing the last defect better than the oracle did |
| `release-back-to-green/` | 8 | the tasks are too small; scale, realism and more verification surfaces will raise the horizon | refuted — 2× defects, 3.3× surface and 3× gates bought 1.9× cost; cost tracks distinct diagnoses alone ([COST_SCALING.md](../../COST_SCALING.md)) |

Trial logs, rewards and submitted artifacts for every run are in the sibling
`trial-*/` directories. The full runnable versions live in separate
repositories, deliberately kept out of this one; `release-back-to-green/` is at
<https://github.com/ogmanojdev/harbor-release-back-to-green> (private).
