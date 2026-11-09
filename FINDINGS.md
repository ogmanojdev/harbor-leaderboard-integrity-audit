# Findings

**The assignment was to build a Harbor task that fairly breaks Claude Opus 5.5.
No task did.** Eleven trials across nine designs scored 1.000 every time, for
$5.57 of a $35 budget.

This page argues the absence is a **result** rather than an omission, because
each trial was built to kill a specific hypothesis about what makes an agent
task hard — and each one did, with numbers. Eight hypotheses, eight refutations,
four laws.

---

## Law 1 — the one-shot defeat condition

> A task resists one-shot solving only when the information required for step
> N+1 does not exist until step N has executed.

Five mechanisms were tried and refuted (trials 1-7): no feedback loop, context
exhaustion, budgeted sequential search, epistemic overclaiming, and a blind spot
in the model's own observed method.

The sharpest one: **volume only exhausts context if the agent holds the
content.** Trial 2 gave it more archive than fits in a window; it wrote a program
to read the archives instead. **Scale punishes humans, not programs.**

Trial 7 — a real service that genuinely does not work — produced the only
authentic diagnose-fix-rerun loop of the eleven, and a fix *better* than the
reference solution's.

## Law 2 — the cost law

> Cost tracks the number of distinct diagnoses a task requires, and nothing else.

Trial 8 moved three variables at once against trial 7:

| | trial 7 | trial 8 | change |
|---|---:|---:|---|
| planted defects | 4 | 8 | 2x |
| source surface | 4,605 LOC | 15,256 LOC | 3.3x |
| verification surfaces | 1 | 3 | 3x |
| **cost per defect** | **$0.103** | **$0.099** | **flat** |
| **tool calls per defect** | **3.75** | **3.75** | **identical** |

Scale, realism and breadth buy nothing. Reaching the horizon the $35 budget
implies would need 30-100 planted defects in one task — a scavenger hunt, not a
long horizon.

## Law 3 — the ambiguity law

> The only lever that changes cost *per unit of work* is specification
> ambiguity, and a fair task may not pull it.

Trials 9 and 10 are the same task on the same container and corpus with exactly
one variable changed — one specification ambiguity removed:

| | trial 9 | trial 10 | change |
|---|---:|---:|---|
| cost | $0.834 | $0.483 | **-42%** |
| output tokens | 17,128 | 7,914 | **-54%** |

Ambiguity resolution, not planning, was the expensive part. **Everything the
brief encourages was measured and did nothing; the one thing that works is
disqualifying**, since vague instructions and hidden requirements are ruled out
by name.

## Law 4 — the fairness ceiling

> A fair task discriminates only when the author's solution lies outside
> standard technique — but then the author usually cannot prove reachability
> either, and shipping an unproven gate is itself disqualifying.

Trial 11 was built to break Law 2 by changing the axis entirely: optimisation
against a verifiable numeric objective, nothing planted, nothing hidden,
authored code as the deliverable, and a threshold placed just past where a
competent single pass lands. The task was to beat a published 144-bit Sudoku
codec; the gate was 108 bits, with the obvious single insight landing at 111 and
scoring 0.458.

It scored 1.000 at exactly 108 bits in **6 tool calls and $0.273**. The constant
barely moved — **3.0 calls per insight against 3.75 per defect** — so the cost
law is not a property of defect-finding tasks. It is a property of how the model
works: read precisely, diagnose locally, emit the minimum.

Two attempts to harden that task were then measured and both failed: joint
ranking buys 1 bit (107) and is not implementable, and grading on adversarially
chosen isomorphs does nothing — across 18,000 valid puzzles neither codec ever
exceeds 108 bits. **108 is the frontier, so no fair gate sits below it.**

---

## Eleven trials

| # | design | result | hypothesis it refuted |
|---|---|---|---|
| 1 | leaderboard audit | 1.000 | no feedback loop |
| 2 | backfill, exactly-once | 1.000 | context exhaustion |
| 3-4 | regression in 12 / 10 runs | 1.000 | budgeted sequential search |
| 5 | calibration | 1.000 | epistemic overclaiming |
| 6 | two causes | 1.000 | a blind spot in its own method |
| 7 | pipeline repair | 1.000 | — the only genuine diagnose-fix loop |
| 8 | release-back-to-green | 1.000 | **scale, realism, breadth** → Law 2 |
| 9-10 | comparable-baseline-plan | 1.000 | planning; isolated **ambiguity** → Law 3 |
| 11 | sudoku-codec-frontier | 1.000 | **threshold placement** → Law 4 |

Every figure above is taken from the committed `result.json` of the run it
describes; `evidence/` holds the logs, rewards, artifacts and trajectories.

## Three places this work argues against itself

1. **Trial 8 was built to refute trial 7's conclusion.** Trial 7 suggested
   bigger, more realistic tasks would cost more. Trial 8 tested that and it is
   false.
2. **Trial 11 was built to refute Law 2**, on an axis Law 2 had never been
   measured on. Law 2 survived.
3. **A calibrator was wrong before a gate was.** The first self-delimitation
   calibrator passed a codec it should have failed — it re-formatted the
   codeword to the same width, reproducing the original prefix. The gate was
   right and the test was wrong. Calibrators test the grader, not the wording.

## The open lead, and why it was not taken

`COST_SCALING.md` rejected many-defect tasks because they do not raise **cost**
efficiently. But "breaks the model" is a question about **failure rate**, not
cost, and that was never tested — failure by accumulation is a different
mechanism from failure by insight. Trial 8 only reached 8 defects.

A 30-defect task is the clearest remaining lead. It was not attempted because it
is a gamble against the submission deadline, and shipping an unvalidated task
would contradict the standard the rest of this work is held to. It is recorded
as an open lead rather than quietly omitted.

## Where to read more

| document | what it covers |
|---|---|
| [`RUN_REPORT.md`](RUN_REPORT.md) | The submitted task in full: fairness rationale, verifier design, shortcut-resistance, calibration, limitations, provenance. §8 is the model runs. |
| [`COST_SCALING.md`](COST_SCALING.md) | Trial 8 as a controlled experiment, and trials 9-10 as the ambiguity pair. Laws 2 and 3. |
| [`SUDOKU_CODEC.md`](SUDOKU_CODEC.md) | Trial 11: the axis change, the measured 648 → 144 → 111 → 108 → 15.58-bit ladder, and two refuted attempts to harden it. Law 4. |
| [`evidence/`](evidence/) | Every trial's logs, rewards, artifacts and trajectories. |
