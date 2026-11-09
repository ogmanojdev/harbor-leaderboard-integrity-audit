# A task on a different axis — `sudoku-codec-frontier`

Ten target-model trials across eight task designs scored 1.000 every time.
`COST_SCALING.md` explains the mechanism: cost tracks the number of distinct
diagnoses a task demands and nothing else, and the only lever measured to change
cost *per unit of work* was specification ambiguity — which a fair task may not
pull, because the brief disqualifies vague instructions and hidden requirements
by name.

Every one of those eight designs was defect-finding or plan-writing. This ninth
design changes the axis instead of the amount.

## The substrate

Pavan Tirumani's [*Sudoku in six pixels*](https://pavan.ink/sudoku-in-six-pixels)
encodes a 17-clue minimum Sudoku in **144 bits** — six 24-bit RGB pixels. For
each digit 1-9 it lists the cell positions holding that digit, lays the nine
lists end to end with markers between them, writes each position as 7 bits with
a leading `1`, and each marker as a single `0`:

    17 positions x (1 + 7) bits + 8 separators = 144 bits

The agent is given that scheme as working code and asked to beat it.

### The article is correct, and checking that came first

A task premised on a planted flaw in someone's published work would be unfair as
well as wrong, so the scheme was checked before anything was designed around it.
The case that looks like a bug is a puzzle using only 8 distinct digits — nine
groups, but one of them empty. It is not a corner case: **23,783 of the 49,151
puzzles in the catalogue, 48%, use only 8 distinct digits.** The encoding
handles it exactly: nine groups need eight separators however they are filled,
the absent digit is an empty group written as two adjacent `0` markers, and the
total stays 144 bits. Verified over all 49,151.

So the task is *beat it*, not *fix it*.

## Why this axis can do what the other eight could not

A defect-finding task has a binary answer the author plants and the agent finds.
An optimisation task against a verifiable objective has a *frontier*, and a
threshold can be placed at a chosen point on it — specifically, **just past
where a competent single pass lands.**

The ladder below is measured, not estimated. Every figure is an exact
mixed-radix or combinatorial bit count over the full 49,151-puzzle catalogue,
with no coder overhead and no sampling.

| approach | codeword | note |
|---|---:|---|
| 81-char UTF-8 string | 648 bits | the article's own baseline |
| 81-bit mask + 4 bits per digit | 149 bits | **worse than the article** |
| the article's scheme | 144 bits | given to the agent, working |
| rank the position *set*; digits still free | 111 bits | the obvious insight. **Misses the target — scores 0.458** |
| **+ digits coded against row/column/box candidates** | **108 bits** | **the target. Oracle: 1.000** |
| if the catalogue were enumerable | 15.58 bits | true floor, computationally unreachable |

The first insight is that the 17 clue positions are an unordered **set** —
log2 C(81,17) = 56.83 bits, not 17 seven-bit integers. That alone is a 33-bit
win over the article and it is where a competent single pass stops. It scores
0.458.

Passing requires a second, independent observation: **a clue's digit is not a
free choice out of nine.** The decoder recovers every position before it reads a
single digit, so each digit can be coded against only those values its row,
column and box still permit — 49.4 bits instead of 17 x log2(9) = 53.9. Folding
both into one mixed-radix integer avoids per-field rounding and lands on exactly
108.

Both halves must be **authored** — a combinatorial ranking function and a
mixed-radix composition — and authored code was the one thing the earlier
measurements found that actually raises output tokens.

### The gap at the top is the interesting part

There are only 49,151 known 17-clue Sudokus, so the Shannon content of "which
17-clue puzzle" is about **15.58 bits**. Reaching it would require enumerating
the catalogue, which is the exhaustive search behind McGuire, Tugemann and
Civario's 2012 proof that no 16-clue puzzle exists. The information-theoretic
optimum is roughly seven times smaller than the best computable codec here, and
unreachable. The task says so openly rather than hiding it.

## Three things that had to be got right

### 1. The published corpus is unsafe to grade on as-is

Royle's catalogue is partially canonicalised, and the artefact is measurable:
the first clue in reading order is digit `1` in **6,820** puzzles but `9` in only
**1,825**. An adaptive codec would learn that skew and score well here while
transferring to nothing — it would be fitting how the list was built, not the
structure of Sudoku.

Each puzzle therefore gets one random Sudoku isomorphism: digit relabelling,
row-within-band and column-within-stack permutation, band and stack permutation,
and optional transpose. All of these map a valid 17-clue puzzle to a valid
17-clue puzzle and preserve uniqueness of the solution. After the transform the
first-clue digit is near-uniform (~5,400 each), no two puzzles collide, and all
49,151 still carry exactly 17 clues. Fixed seed; `environment/data/PROVENANCE.md`
records the source URL, its sha256 and the reproduction command.

### 2. The catalogue shortcut is closed by construction, not by rule

An index into the 49,151 known puzzles is ~16 bits and is *genuinely lossless*
on any subset of them. A rule forbidding it would be unenforceable, so it is
closed three ways at once:

- the 10,000 graded puzzles are **not** in the agent's 39,151-puzzle corpus;
- only **one file** is collected for grading, so a companion data blob simply
  would not exist in the verifier;
- that file is capped at **64 KB**, and a catalogue cannot fit — the puzzles
  alone need more than 600 KB however they are coded.

### 3. A fixed-length codeword, so nothing rides in the length

A variable-length codec graded on *mean* bits can smuggle information into the
length of its own output. The requirement is therefore a **fixed** codeword,
which is also exactly the article's framing — one puzzle, a whole number of
pixels — and it removes the loophole rather than policing it.

A fixed length has a second benefit: it needs no statistical margin. The oracle
emits exactly 108 bits for **every** puzzle in the catalogue, verified
exhaustively, so a `<= 108` gate is provably reachable rather than reachable on
average.

The matching requirement is **self-delimitation**: `decode` must read only the
first `BITS` characters. The grader appends random padding and demands the same
answer, which is what makes "fixed length" mean something.

## Verifier design

Separate verifier container, `no-network` in both phases, one declared artifact
crossing the boundary. All reward values are numeric, as Harbor requires;
diagnostics go to `/logs/verifier/report.txt`.

| dimension | meaning |
|---|---|
| `losslessness` | `decode(encode(p)) == p` on all 10,000 held-out puzzles |
| `fixed_length` | one codeword length for all puzzles, equal to the declared `BITS` |
| `self_delimiting` | `decode` reads only the first `BITS` chars, tested with random padding |
| `size_limit` | submitted file is 64 KB or less |
| `target_met` | `BITS <= 108` |
| `bits`, `pixels`, `compression_vs_article`, `stretch_met` | reported for measurement |

`overall` is 0 unless every gate passes; then 1.0 at or below 108 bits, and
partial credit scaled across the 144 → 108 gap for a codec that beats the
article without reaching the target.

### One integrity property is weaker here, and it is worth naming

The other task's verifier never executes agent-authored code — it reads
artifacts. Measuring a *codec* unavoidably means running the agent's code inside
the grading container. Three mitigations, and the residual risk stated plainly:

- the codec runs in a **subprocess**, as **`nobody`**, with its working
  directory in `/tmp`;
- the grader writes `reward.json` **after** that subprocess has exited, so
  anything written to that path while the codec ran is overwritten;
- the container has no network in either phase.

Residual: a submission that escaped the subprocess *before* the grader's final
write could still affect the grade. Closing that completely would need a second
container or a seccomp profile, and it is not closed here.

### The shared gate module

`gates.py` is byte-identical between `environment/reference/` (the practice
harness the agent runs) and `tests/` (the grader). A task whose practice harness
and grader can disagree is a task that fails agents for the wrong reason.

## Calibration against deliberately wrong solutions

Nine calibrators, run through the real grader. The earlier lesson was that
calibrators test the *grader*, not the wording — so each one targets a specific
gate.

| calibrator | `overall` | bits | gate that caught it |
|---|---:|---:|---|
| oracle (108 bits) | **1.0000** | 108 | — passes, as it must |
| naive: set-ranked positions, free digits | 0.4583 | 111 | none — beats the article, misses the target |
| the article's own scheme | 0.0000 | 144 | none — valid but no improvement |
| lossy (drops a clue) | 0.0000 | — | `losslessness` |
| variable-length | 0.0000 | — | `fixed_length` |
| end-anchored decode | 0.0000 | 108 | `self_delimiting` |
| trailing-bit dependent decode | 0.0000 | 108 | `self_delimiting` |
| 70 KB source | 0.0000 | — | `size_limit` |
| raises on some inputs | 0.0000 | — | measurement error path |

The first attempt at the `self_delimiting` calibrator was itself wrong — it
re-formatted the codeword integer to the same width, which reproduces the
original prefix, so it passed. The gate was right and the test was wrong. It
was replaced with two genuine violators.

## Model runs

### Oracle

End-to-end through Harbor: **108 bits, `overall` 1.000**, every gate green, 58
seconds. `harbor lint` clean at default rules; `--select ALL` surfaces only
`unpinned-image` and `root-agent`, the same two the submitted task carries.
Evidence in `evidence/sudoku-oracle/`.

The artifact arrived in the verifier at `/app/submission/codec.py` — the source
path, not the declared `destination` — which is why the grader searches several
roots.

### Target model: Claude Opus 5.5

**Trial 11. `overall` 1.000, exactly 108 bits, 6 tool calls, $0.273, 3m 22s.**
Evidence in `evidence/trial-11-sudoku-codec-frontier/`.

The threshold did not discriminate. The hypothesis stated in this document
before the run — that a threshold placed just past a competent single pass
would be the first fair mechanism to produce a failure — is **refuted**.

What makes the refutation informative is *how* it failed. The model did not
stumble into 108; it went looking for the frontier:

| call | what it did |
|---|---|
| 1 | read the stub, the harness, the corpus |
| 2 | built the peer sets and measured the constraint structure directly |
| 3 | measured the cost distribution over the training corpus |
| 4 | Monte Carlo over 200,000 random 17-cell subsets |
| 5 | probed the distribution tail at 49.6, 49.8, 50.0, 50.2, 50.4, 50.6 bits |
| 6 | wrote the codec |

Call 5 is the one that matters. Sizing a fixed-length codeword requires the
**worst case**, not the mean, and the model went after the tail deliberately
rather than fitting the average and hoping. That is the step a solution scoring
0.458 would have skipped.

It also found both insights independently — the position set ranked in the
combinatorial number system, and digits coded against row/column/box candidates
— and then added a refinement the oracle does not have: an **adaptive
most-constrained-first visiting order**, reproducible by the decoder from the
digits it has already placed.

That refinement bought exactly **zero bits**, which was measured independently
during design: most-constrained-first moves the worst-case digit cost from 50.81
to 50.57 bits, and both round to the same 108-bit codeword. Two independent
constructions, one with a sophistication the other lacks, landing on the
identical number is reasonable evidence that **108 is the real frontier for this
family of codes**, not an artefact of either implementation.

### The cost law survives a change of axis

This is the result worth keeping. `COST_SCALING.md` measured, on
defect-finding tasks, that cost tracks the number of distinct diagnoses at about
**3.75 tool calls and ~$0.10 per diagnosis**, invariant to scale, realism and
gate count.

This task is not defect-finding. Nothing is planted, nothing is hidden, the
deliverable is authored code rather than a patch, and the objective is numeric.
The law holds anyway:

| | defect-finding (trials 7, 8) | this task |
|---|---|---|
| units of work | 4 and 8 defects | 2 insights |
| tool calls per unit | 3.75, 3.75 | **3.0** |
| cost per unit | ~$0.10 | **~$0.137** |

Two insights at three calls each. The axis changed and the constant did not,
which makes the law look less like a property of defect-finding tasks and more
like a property of how the model works: read precisely, diagnose locally, emit
the minimum. An eleventh 1.000 at $0.27 is the same measurement arriving by a
new route.

### What would actually be needed

The honest conclusion is that **108 was reachable in one pass because both
insights are standard**. Combinatorial ranking and constraint-aware coding are
textbook; the task asked for assembly, not discovery. A threshold that
discriminates would have to sit where no standard technique reaches — below
roughly 100 bits, which requires exploiting the uniqueness-of-solution
constraint during coding, so the encoder and decoder must each run a Sudoku
solver and spend bits only on choices propagation cannot force.

### Two attempts to harden the task, both refuted

Asked whether the task could be pushed further, two concrete attacks were tried
and measured rather than assumed.

**Lower the threshold to 107 by joint ranking.** The shipped construction pays
`log2 C(81,17)` for the position set plus the *worst-case* digit cost, because a
fixed-length codeword must cover the worst case: 56.83 + 50.69 → 108. Ranking
the (position set, labelling) pairs *jointly* pays the **mean** instead of the
worst case — 56.83 + 49.41 = 106.25 → **107 bits**. One bit, and it is not
implementable: the ranking needs prefix sums of the labelling count over all
C(81,17) = 1.28 x 10^17 position sets.

**Grade on adversarially-chosen isomorphs.** The corpus applies one random
isomorphism per puzzle. The oracle visits clues in reading order, so its digit
cost is *not* isomorphism-invariant, and a hostile choice of isomorph looked
like it might push a 108-bit codec into overflow — failing a submission sized to
the corpus. Measured over **18,000 valid 17-clue puzzles** (300 catalogue
puzzles x 60 isomorphs each): the worst case is **108 bits for both codecs**,
with zero overflows. The attack does not exist. The model's most-constrained-first
ordering would have been immune regardless, since the visiting order it induces
is a function of the isomorphism-invariant peer graph.

So 108 is not an artefact of one construction, one ordering, or one sampling of
the isomorphism group. **It is the frontier**, and there is no fair gate below it.

That threshold is **not shipped, because it is not proven reachable**. Setting a
gate at a number the author has not hit would be exactly the unvalidated task
the rest of this repository argues against. It is recorded here as the next
experiment, not as a requirement.

## Limitations, stated plainly

- **The discrimination hypothesis is refuted, not supported.** The threshold was
  cleared in one pass. This task adds a confirmation of the cost law on a new
  axis; it does not add a failure.
- **108 is proven over the catalogue, not over all 17-clue Sudokus.** The bound
  is empirical: the worst case across all 49,151 known puzzles. No 17-clue
  puzzle has been found since 2009 and the catalogue is believed complete, but
  "believed complete" is not "proven complete".
- **96 bits is a stretch with no known solution.** It is reported, never
  required, and named in the instruction precisely so the target cannot be
  mistaken for something secretly lower.
- **The agent's code runs in the grading container.** See above.
- **The task cannot be hardened without becoming unfair.** The two attacks above
  are refuted and the next real gain needs enumeration, so any gate below 108
  would be a number the author has not reached.
- **One task, one axis.** This design tests whether an optimisation threshold
  discriminates. It does not re-open the cost question, and it should not be
  read as a cost result.

## Reproduction

```bash
# Oracle
harbor run -c job-sudoku.yaml -a oracle --yes --job-name sudoku-oracle

# Target model (needs an OpenRouter key in the environment)
harbor run -c job-sudoku.yaml -a claude-code \
    -m anthropic/claude-opus-5.5 --base-url https://openrouter.ai/api \
    --yes --job-name sudoku-opus

harbor view jobs
```

`harbor run` has no `--task-path` flag and `-t/--task` parses as a package
reference, so the task is pointed at by path from `job-sudoku.yaml`. Agent and
model stay on the command line: agent keys set in the YAML are dropped from the
resolved config.

The measurement scripts behind the ladder and the corpus transform live in
`sudoku-codec-frontier/environment/data/build_corpus.py` and
`sudoku-codec-frontier/environment/reference/`.
