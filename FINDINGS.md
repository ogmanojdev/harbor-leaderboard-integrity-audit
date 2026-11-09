# Findings

**The assignment was to build a Harbor task that fairly breaks Claude Opus 5.5.
No task did.** Eleven trials across nine designs scored 1.000 every time, and a
twelfth measurement refuted the most promising mechanism left, for $5.63 of a
$35 budget.

This page argues the absence is a **result** rather than an omission, because
each trial was built to kill a specific hypothesis about what makes an agent
task hard — and each one did, with numbers. Nine hypotheses, nine refutations,
five laws.

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
competent single pass lands. The task was to beat the published 144-bit Sudoku
codec in Pavan Tirumani's [*Sudoku in six pixels*](https://pavan.ink/sudoku-in-six-pixels);
the gate was 108 bits, with the obvious single insight landing at 111 and
scoring 0.458.

It scored 1.000 at exactly 108 bits in **6 tool calls and $0.273**. The constant
barely moved — **3.0 calls per insight against 3.75 per defect** — so the cost
law is not a property of defect-finding tasks. It is a property of how the model
works: read precisely, diagnose locally, emit the minimum.

Two attempts to harden that task were then measured and both failed: joint
ranking buys 1 bit (107) and is not implementable, and grading on adversarially
chosen isomorphs does nothing — across 18,000 valid puzzles neither codec ever
exceeds 108 bits. **108 is the frontier, so no fair gate sits below it.**

## Law 5 — reachability precedes discrimination

> A gate the author's own solution cannot pass is unfalsifiable, not hard — and
> that is a check on the arithmetic of the source, not something a trial finds.

Law 4 appears to leave one escape: make the gate **binary** rather than
thresholded. Trial 11's weakness was that 108 bits is a point on a cost
distribution, so the model probed the tail on purpose and sized its codeword to
the worst case. An *exact* objective has no tail to probe — a floating-point
optimiser returns 0.8707376… and can never certify that it equals
(81−√1537)/48. The twelfth measurement tested that escape on the strongest
substrate available.

Substrate: the October 2026 quasi-Riemann hypothesis results, and the follow-up
[arXiv:2610.12234v1](https://arxiv.org/html/2610.12234v1) (Liu, Purdue), which
sharpens the zero-free half-plane constant 7/8 by 4.293×10⁻⁵ to
B_new = (1507−2√921)/1653. Real, exactly verifiable, provable oracle.

**The design's own constraint set turned out to contain an unreachable gate, and
arithmetic on the source caught it before any build time was spent.** The
piecewise-linear exponent (d_J + 5ℓ − 1)/4 vanishes across every subset
dimension 0 ≤ d_J ≤ ℓ exactly when 6ℓ ≤ 1, and ℓ = 1/6 saturates that with
equality — which is *why* B = 7/8 is the convenient choice. But
6ℓ_new = 1.00103 > 1: the published optimum lies **outside** the constraint the
design named, because Liu's Part III replaces it with E = 0 at the critical zero
class R\* = 2/3 plus a stationarity condition. A verifier built from the stated
constraints would have rejected its own oracle by 1.03×10⁻³.

So the probe used a reachability-provable surrogate — same idiom, two explicitly
binding margin constraints, and an optimum **published nowhere**, so recall is
unavailable by construction:

> minimise B(ℓ) = 11/12 − ℓ/4 over δ ∈ (0, 1/2], subject to
> **(C1)** critical-class feasibility, ℓ ≤ (5 − 6δ)/(9 + 18δ), and
> **(C2)** strict saving margin, ℓ ≤ (1 + 3δ)/(7 + 12δ).

| quantity | derived by hand | Opus 5.5, first pass |
|---|---|---|
| δ_c | (√1537 − 9)/84 | ✓ |
| ℓ\* | (√1537 − 37)/12 | ✓ |
| B\* | (81 − √1537)/48 | ✓ |
| minimal polynomial of B\* | 72x² − 243x + 157 | ✓ |
| margin over 7/8 | (√1537 − 39)/48 | ✓ |

**No floating point anywhere; `scipy` was never reached for.** The derivation was
sound rather than a lucky landing — it proved the two bounds strictly decreasing
and strictly increasing, checked both endpoints to establish a unique interior
crossing, argued that the minimum of an increasing and a decreasing function is
maximised where they cross, reduced to 126δ² + 27δ − 26 = 0, and observed that
the discriminant 13833 = 9 × 1537 with 1537 = 29 × 53 squarefree.

**The premise under test was the author's own, and it was false.** The design
predicted failure "by using `scipy.optimize` floating-point approximations that
violate the strict saving margin". On a margin-critical algebraic optimum the
model works exactly by default. The binary gate does not discriminate — not
because it is probeable, but because **the model never lands on the wrong side of
it.** Law 2 now holds across four axes: defect-finding, planning, open-ended
optimisation, and exact algebra.

A second result came free. Asked for B_new cold, with a confident premise and a
specific-looking constant implied, the model said it had no record of the result
and declined to invent one — then challenged the premise on correct grounds, that
the known unconditional results are Vinogradov–Korobov zero-free *regions*
shrinking toward Re s = 1 rather than fixed half-planes. That is a sixth data
point against trial 5's hypothesis: a task built to catch fabrication on
post-cutoff mathematics would not discriminate either.

**Stated precisely:** this was two single-shot API calls costing $0.0541, not a
Harbor agentic run, so it is a capability measurement rather than a twelfth
trial. What it refutes is a claim about the model's default method, not a claim
about agentic cost. Full derivation, both transcripts and the three source errors
found along the way are in
[`evidence/probes/qrh-exponent-optimiser/`](evidence/probes/qrh-exponent-optimiser/).

---

## Eleven trials and a twelfth measurement

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
| 12* | QRH exponent optimiser | exact, 1 pass | **exact algebra / binary gates** → Law 5 |

\* A capability probe, not a Harbor run — see Law 5.

Every figure above is taken from the committed `result.json` of the run it
describes; `evidence/` holds the logs, rewards, artifacts and trajectories.

## Five places this work argues against itself

1. **Trial 8 was built to refute trial 7's conclusion.** Trial 7 suggested
   bigger, more realistic tasks would cost more. Trial 8 tested that and it is
   false.
2. **Trial 11 was built to refute Law 2**, on an axis Law 2 had never been
   measured on. Law 2 survived.
3. **A calibrator was wrong before a gate was.** The first self-delimitation
   calibrator passed a codec it should have failed — it re-formatted the
   codeword to the same width, reproducing the original prefix. The gate was
   right and the test was wrong. Calibrators test the grader, not the wording.
4. **A rubric evaluator found a 1.000-scoring exploit that nine calibrators
   missed.** Trial 11's grader originally ran `encode` and `decode` in one
   process, so a codec keeping a module-level dict could emit 14-bit codewords
   and pass every gate — beating even the stretch tier while compressing
   nothing. Confirmed at **1.0000 at 14 bits**, then closed structurally: the
   codec now runs in four isolated processes, the decode processes receive
   codewords and nothing else, the parent imports none of the submission, and
   the held-out corpus is unreadable by the child processes. Trial 11's own
   submission was re-graded and still scores 1.000, so the result stands.

   Then the **second** round found the fix incomplete — the stray-file scan
   covered only each phase's own directory, and a codec can hardcode `/tmp`.
   Confirmed at 1.0000 at 14 bits again, and closed by enumerating every
   world-writable directory and purging between phases. Third round: **11 of
   11**.

   The generalisation: hand-written calibrators test only the holes their author
   already imagined, and a patch that looks sufficient usually isn't. Both holes
   were found by pointing a different kind of reader at the verifier; neither by
   the author writing tests against their own design.

5. **The twelfth measurement killed the best-looking mechanism left, and the
   design error was the author's.** Exact algebra over a published research
   result was the one remaining idea that escaped Law 4 on paper. Verifying the
   substrate first turned up three errors in the author's own framing — a margin
   attributed to the wrong object, a prime-gap result that does not chain off the
   improved constant, and a constraint set that cannot reach the optimum it was
   written to verify. The mechanism was then measured and refuted in two API
   calls for four cents, rather than after a day of building.

## Two open leads, and why neither was taken

### 1 — failure by accumulation

`COST_SCALING.md` rejected many-defect tasks because they do not raise **cost**
efficiently. But "breaks the model" is a question about **failure rate**, not
cost, and that was never tested — failure by accumulation is a different
mechanism from failure by insight. Trial 8 only reached 8 defects.

A 30-defect task is the clearest remaining lead. It was not attempted because it
is a gamble against the submission deadline, and shipping an unvalidated task
would contradict the standard the rest of this work is held to. It is recorded
as an open lead rather than quietly omitted.

### 2 — undisclosed expert knowledge

This is the lead I would take first, because it is the only one that escapes
Law 4 rather than working around it.

Law 4 says a fair task discriminates only when the author's solution lies
outside standard technique — but that the author then usually cannot prove the
gate is reachable, and shipping an unproven gate is itself disqualifying. That
is a genuine trap, and **undisclosed expertise dissolves it**: a practitioner
who has already solved the problem *is* the proof of reachability. The solution
exists and has been verified by someone. It simply is not in the papers, and so
is not in the training data.

The published failure analysis points the same way. On FrontierPhysics, only
**11%** of Opus 5.5's failures were knowledge gaps, while **34%** were missing
expert intuition and **48%** non-rigorous reasoning. The gap is not facts. It is
the judgement that accumulates in people who do the work and never quite gets
written down.

The concrete instance I would build: a friend of mine works on noise suppression
in audio AI and has arrived at insights about how to construct those models that
are not in any paper I can find. The task would hand an agent the same starting
materials — corpora, metrics, baselines — and ask it to design models, run
experiments and reach a specification a group of practitioners cracked, or to
move a public leaderboard that is pushed every year. Training and evaluation
cycles are expensive by nature, which also attacks Laws 2 and 3 from a direction
nothing else here reached: experiments cost real wall-clock time and cannot be
collapsed by reading precisely and emitting the minimum.

**The hard part, stated honestly.** Undisclosed knowledge is only fair if the
*evidence* the expert reasoned from is in the container and only the *synthesis*
is withheld. Withhold the evidence too and it stops being a hard task and
becomes a guess — the same line the network-fault idea crossed at the very
start. Getting that boundary right needs the expert's time, their consent to
encode unpublished judgement in a public artifact, a deterministic verifier over
experimental results rather than over a text answer, and a GPU budget. None of
those fit a one-week window, which is why it is written down rather than
attempted.

**The variant I rejected: recency.** The obvious cheaper version is to use
something simply too new to be in the training data — the AI-generated proof of
the [quasi-Riemann hypothesis](https://www.quantamagazine.org/ai-proved-the-quasi-riemann-hypothesis-what-happens-now-20261019/),
announced in October 2026 and still being checked by Sarnak, Radziwiłł and
Dunn, postdates this model. A task built on it would almost certainly produce a
failure.

It would be the wrong failure. It measures a training cutoff, not a capability:
on FrontierPhysics, knowledge gaps were the *smallest* slice of failures at 11%,
and a gap that closes itself at the next release is not a finding. Worse, it
crosses the same line the network-fault idea crossed — the answer is not
derivable from anything in the container, so the agent is guessing rather than
reasoning.

That episode also sharpens why the expertise lead is about **undisclosed**
rather than **unpublished**. The quasi-Riemann proof was produced by a machine
and is being verified by humans, so "beyond standard technique" is no longer a
line between human insight and machine reasoning. The durable boundary is
narrower: judgement that was never written down at all, held by people who use
it daily and have no reason to publish it. Recency expires. Tacit knowledge does
not.

## Where to read more

| document | what it covers |
|---|---|
| [`RUN_REPORT.md`](RUN_REPORT.md) | The submitted task in full: fairness rationale, verifier design, shortcut-resistance, calibration, limitations, provenance. §8 is the model runs. |
| [`COST_SCALING.md`](COST_SCALING.md) | Trial 8 as a controlled experiment, and trials 9-10 as the ambiguity pair. Laws 2 and 3. |
| [`SUDOKU_CODEC.md`](SUDOKU_CODEC.md) | Trial 11: the axis change, the measured 648 → 144 → 111 → 108 → 15.58-bit ladder, and two refuted attempts to harden it. Law 4. |
| [`evidence/`](evidence/) | Every trial's logs, rewards, artifacts and trajectories. |
