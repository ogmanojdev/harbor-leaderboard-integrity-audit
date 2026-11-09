# collinear-candidate/sudoku-codec-frontier

An agent is given a published Sudoku compression scheme — **144 bits, six RGB
pixels**, from Pavan Tirumani's [*Sudoku in six
pixels*](https://pavan.ink/sudoku-in-six-pixels) — as working code, and asked to
beat it: a lossless, fixed-length, self-delimiting codec for 17-clue Sudoku at
**108 bits or fewer**, graded on 10,000 held-out puzzles.

```bash
harbor run -c ../job-sudoku.yaml -a oracle --yes
harbor run -c ../job-sudoku.yaml -a claude-code \
    -m anthropic/claude-opus-5.5 --base-url https://openrouter.ai/api --yes
```

Oracle scores **1.000** at exactly 108 bits. `harbor lint` clean.

## Why this task exists

The other eight task designs in this repository are defect-finding or
plan-writing, and all ten target-model trials scored 1.000. `COST_SCALING.md`
explains why: cost tracks the number of distinct diagnoses a task requires, and
the only lever that moved cost per unit of work was specification ambiguity —
the one lever a fair task may not pull.

This task changes the axis rather than the amount. It is not defect-finding:
nothing is planted and nothing is hidden. It is **optimisation against a
verifiable objective**, which admits something the earlier designs could not
express — a threshold placed *just past where a competent single pass lands*.

That distinction is the whole design, and it is measurable:

| approach | codeword | outcome |
|---|---:|---|
| 81-char UTF-8 string | 648 bits | the article's own baseline |
| 81-bit mask + 4 bits per digit | 149 bits | **worse** than the article |
| the article's scheme | 144 bits | given to the agent as working code |
| rank the position *set*, digits still free | 111 bits | beats the article, **misses the target** (scores 0.458) |
| **+ digits constrained by row/column/box** | **108 bits** | **the target. Oracle.** |
| if the 49,151-puzzle catalogue were enumerable | 15.58 bits | the true floor, computationally unreachable |

The obvious insight — that 17 clue positions are an unordered set carrying
log2 C(81,17) = 56.83 bits, not 17 seven-bit integers — gets you to 111 and
**fails**. Passing also requires noticing that a clue's digit is not a free
choice out of nine: the decoder knows every position before it reads any digit,
so each digit can be coded against the candidates its row, column and box still
permit. That is 49.4 bits instead of 17 x log2(9) = 53.9.

Both halves must be *authored* — a combinatorial ranking function and a
mixed-radix composition — which is the one thing the earlier measurements found
that actually raises output tokens.

## What is measured

Five gates, then one number. All reward values are numeric, as Harbor requires;
diagnostics go to `/logs/verifier/report.txt`.

| dimension | meaning |
|---|---|
| `losslessness` | `decode(encode(p)) == p` on all 10,000 held-out puzzles |
| `fixed_length` | one codeword length for every puzzle, equal to the declared `BITS` |
| `self_delimiting` | `decode` reads only the first `BITS` characters — verified by appending random padding |
| `size_limit` | the submitted file is 64 KB or less |
| `target_met` | `BITS <= 108` |
| `bits`, `pixels`, `compression_vs_article`, `stretch_met` | reported for measurement |

`overall` is 0 unless every gate passes; then 1.0 at or below 108 bits, and
partial credit scaled across the 144→108 gap for a codec that beats the article
without reaching the target.

## Two things that had to be got right

**The corpus is not used as published.** Royle's catalogue of 49,151 17-clue
Sudokus is partially canonicalised, and the artefact is measurable: the first
clue in reading order is digit `1` in 6,820 puzzles but `9` in only 1,825. A
codec tuned on that would be fitting the catalogue's construction rather than
the structure of Sudoku. Every puzzle therefore gets one random Sudoku
isomorphism — digit relabelling, row/column/band/stack permutation, optional
transpose — all of which preserve validity and uniqueness. After the transform
the first-clue digit is near-uniform. See `environment/data/PROVENANCE.md`.

**The catalogue shortcut is closed by construction, not by rule.** There are
only 49,151 known 17-clue puzzles, so an index into them is 15.58 bits and is
genuinely lossless on any subset. It is ruled out three ways at once: the graded
puzzles are not in the agent's corpus, only a single file is collected so a
companion data blob would not exist at grading time, and 64 KB cannot hold a
catalogue — the puzzles alone need more than 600 KB however they are coded.

## A note on the article

The 144-bit scheme is **correct**, and checking that mattered: a task premised
on a planted flaw in someone's published work would be unfair as well as wrong.
The case worth testing is a puzzle using only 8 distinct digits, which is not a
corner case but 48% of the catalogue (23,783 of 49,151) — nine groups still need
only eight separators, the absent digit is an empty group, and the total stays
exactly 144 bits. Verified over all 49,151.

## Layout

```
environment/
  data/            39,151-puzzle training corpus, builder, provenance
  reference/       article_codec.py, gates.py, measure.py
  submission/      codec.py — the deliverable, pre-filled with the article's codec
solution/          the 108-bit oracle and its solve.sh
tests/             the grader, and the 10,000 held-out puzzles
```

`gates.py` is shared verbatim between `environment/reference/` and `tests/` so
the practice harness the agent runs and the grader cannot drift apart.
