# Harbor task design — Collinear candidate submission

**The assignment was to build a Harbor task that fairly breaks Claude Opus 5.5.
No task did.** Eleven target-model trials across nine designs scored 1.000 every
time, for $5.63 of a $35 budget.

> **What is submitted:** the single task directory
> [`leaderboard-integrity-audit/`](leaderboard-integrity-audit/).
> [`sudoku-codec-frontier/`](sudoku-codec-frontier/) is trial 11 — it ships as
> evidence for Law 4 and the verifier-hardening finding, not as a second
> submission.

This repository argues the absence is a **result** rather than an omission.
Each design was built to kill a specific hypothesis about what makes an agent
task hard, and each one did, with numbers:

| | law | the measurement that produced it |
|---|---|---|
| 1 | A task resists one-shot solving only when the information for step N+1 does not exist until step N has executed | five mechanisms predicted, built and refuted (trials 1-7) |
| 2 | Cost tracks the number of distinct diagnoses and nothing else | 2x defects, 3.3x source, 3x verification surfaces → **3.75 calls per defect, unchanged** (trial 8) |
| 3 | The only lever that moves cost per unit of work is specification ambiguity — which a fair task may not pull | one ambiguity removed → **cost −42%, output tokens −54%** (trials 9-10) |
| 4 | A fair task discriminates only where the author's own solution leaves standard technique | axis changed to optimisation against a numeric objective → **3.0 calls per insight, cleared in one pass** (trial 11) |

**→ [`FINDINGS.md`](FINDINGS.md) is the one-page version. Start there.**

## The two tasks

**[`leaderboard-integrity-audit/`](leaderboard-integrity-audit/)** — an agent
audits a GPU benchmark leaderboard for runs that are invalid or not comparable,
publishes a corrected leaderboard, and patches the ingest validator so the same
defects cannot recur. Built on a real LLM-benchmarking backend I designed and
operate ([`corespan/aistudio-server`](https://github.com/corespan/aistudio-server),
Apache-2.0), vendored at a pinned commit. Oracle **1.000** on all five
dimensions; `harbor lint` clean; `harbor check` 11 of 11.

**[`sudoku-codec-frontier/`](sudoku-codec-frontier/)** — an agent is given a
published 144-bit Sudoku compression scheme — Pavan Tirumani's
[*Sudoku in six pixels*](https://pavan.ink/sudoku-in-six-pixels) — as working code and asked to beat
it: a lossless, fixed-length, self-delimiting codec at 108 bits or fewer on
10,000 held-out puzzles, where the obvious single insight lands at 111 and
scores 0.458. Built to test Law 4 by changing the axis away from
defect-finding. Oracle **1.000** at exactly 108 bits — and so is Opus 5.5, in 6
tool calls and $0.273. `harbor check` 11 of 11, after two rounds of its rubric
evaluator finding exploits in the grader that nine hand-written calibrators had
missed.

```bash
harbor run -c job-leaderboard.yaml -a oracle --yes
harbor run -c job-sudoku.yaml      -a oracle --yes

harbor run -c job-sudoku.yaml -a claude-code \
    -m anthropic/claude-opus-5.5 --base-url https://openrouter.ai/api --yes
harbor view jobs
```

## Why there is no failure to report

Opus 5.5 wins these tasks by reading precisely, diagnosing locally, and emitting
the minimum — 3.75 tool calls per defect, invariant across both measured points,
and 3.0 per insight on an axis the law had never been measured on. Reaching the
horizon the $35 budget implies would take 30 to 100 planted defects in one task,
which is a scavenger hunt rather than a long horizon.

The one lever found to change cost *per unit of work* was specification
ambiguity, and that is the lever a fair task is forbidden to pull: the brief
disqualifies vague instructions and hidden requirements by name. **Everything
the brief encourages was measured and did nothing.**

Five failure mechanisms were predicted, built and refuted on the way there.
Three further defect classes died during calibration, one of which was a layer
of the submitted task. On the ninth design the model audited the task's own
specification and found two defects in it that the author had missed. The
clearest remaining lead — failure by *accumulation* rather than by insight — is
stated openly in [`FINDINGS.md`](FINDINGS.md) along with why it was not
gambled against the deadline.

## Reading order

| document | what it covers |
|---|---|
| [`APPROACH.md`](APPROACH.md) | My own account of how this went, written as I went: the first idea I dropped and why, what I read when the first task did not bite, and what I would try next. Unpolished on purpose. |
| [`FINDINGS.md`](FINDINGS.md) | **One page.** The four laws, the eleven-trial table, the four places this work argues against itself, and the open lead. |
| [`RUN_REPORT.md`](RUN_REPORT.md) | The first task in full: fairness rationale, economic realism, verifier design, shortcut-resistance analysis, calibration against deliberately bad solutions, model runs, limitations, provenance. §8 is the model runs. |
| [`COST_SCALING.md`](COST_SCALING.md) | Trial 8 as a controlled experiment and trials 9-10 as the ambiguity pair: the scaling measurement, the falsified prediction about forcing code authoring, three defect classes rejected during calibration, and a grading hole found and closed. Laws 2 and 3. |
| [`SUDOKU_CODEC.md`](SUDOKU_CODEC.md) | Trial 11: the axis change, the measured 648 → 144 → 111 → 108 → 15.58-bit ladder, why the published corpus is unsafe to grade on unmodified, how the catalogue-lookup shortcut is closed by construction, fourteen calibrators, a 1.000-scoring exploit a rubric evaluator found and how it was closed, and two refuted attempts to harden the task. Law 4. |
| [`evidence/`](evidence/) | Every trial's logs, rewards, artifacts and trajectories. `evidence/probes/` holds the designs of the six probe tasks — none is a submission. |

## What is net-new

Both task scenarios, the defect taxonomy, the corpora, the verifiers, the
oracles and every probe design were created for this exercise. The application
under the first task is pre-existing open source of my own authorship, vendored
unmodified at a pinned commit and transformed into a task scenario it was never
built for. The second task's substrate is a published blog post, used as a
documented baseline to beat rather than as a solution to copy; its corpus is
Gordon Royle's public 17-clue catalogue, transformed to remove a canonicalisation
artefact measured in `SUDOKU_CODEC.md`. Full provenance and licence notes are in
`RUN_REPORT.md` §10 and `sudoku-codec-frontier/environment/data/PROVENANCE.md`.

Nothing here is ported from SWE-bench, Terminal-Bench, a public CTF, a Kaggle
notebook, a public issue, or a prior Collinear task.
