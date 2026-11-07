# Probe tasks — evidence, not submissions

The submission contains exactly one task directory: `leaderboard-integrity-audit/`
at the repository root. Nothing here is a Harbor task directory and nothing here
is offered for grading.

These are the two additional tasks built to test hypotheses about what makes a
frontier agent fail, after the submitted task did not. Only the mechanism and
the instruction are reproduced, so the design can be read and checked:

| probe | hypothesis | result |
|---|---|---|
| `backfill-exactly-once/` | volume + a non-idempotent tool will exhaust context | refuted — Opus scripted it, 1m40s |
| `regression-in-twelve-runs/` | irreducible sequential search under a measurement budget | refuted — Opus re-planned and landed exactly on budget, twice |

Trial logs, rewards and submitted artifacts for all four runs are in the sibling
`trial-*/` directories. The full runnable versions live in separate
repositories, deliberately kept out of this one.
