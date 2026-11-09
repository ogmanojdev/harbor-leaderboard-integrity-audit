# Compress a minimum Sudoku below the six-pixel bound

A minimum Sudoku is a 9x9 puzzle with exactly **17 filled clues** — the proven
minimum for a unique solution. In *Sudoku in six pixels*, Pavan Tirumani encodes
one in **144 bits**, which is six 24-bit RGB pixels.

His scheme, which you have as working code in `reference/article_codec.py`:

- For each digit 1-9, list the cell positions (0-80) holding that digit.
- Lay the nine lists end to end with markers between them.
- Write each position as 7 bits with a leading `1`; write each marker as `0`.
- 17 positions x 8 bits + 8 separators = **144 bits**.

It is correct and it round-trips every puzzle in the catalogue. Your job is to
beat it.

## What to build

Write **`/app/submission/codec.py`**, exposing exactly this interface:

```python
BITS = <int>                      # the fixed codeword length, in bits

def encode(puzzle: str) -> str:
    """puzzle: 81 chars, '0' for empty and '1'-'9' for a clue; exactly 17 clues.
    Returns a string of exactly BITS characters, each '0' or '1'."""

def decode(bits: str) -> str:
    """bits: a codeword from encode(), possibly with extra characters appended.
    Returns the original 81-character puzzle."""
```

A stub with this shape is already in place. `reference/measure.py` scores a
codec against the training corpus exactly the way the grader will; run it as
often as you like.

## How your codec is run

`encode` and `decode` are executed in **separate short-lived processes**, and the
decode process is given **codewords and nothing else** — not the puzzles, not any
corpus. Each process runs unprivileged in its own empty directory. Your codec is
imported fresh in each one.

So a codeword must be *self-contained*. Nothing can travel from encoding to
decoding except the bits: not a module-level variable, not a cache, not a file
on disk. `reference/measure.py` runs your codec exactly this way, so you can see
this for yourself.

## Hard requirements

1. **Lossless.** `decode(encode(p)) == p` for every graded puzzle. No exceptions.
2. **Fixed length.** `len(encode(p)) == BITS` for every puzzle, with the same
   `BITS` for all of them. A codeword whose *length* varies would smuggle
   information in that length rather than in the bits.
3. **Self-delimiting.** `decode` must read only the first `BITS` characters.
   The grader appends random padding and requires the same answer.
4. **One file, 64 KB or less.** `/app/submission/codec.py` is the only thing
   collected for grading. Any companion file you write will not be there at
   grading time, so a codec that needs one will fail requirement 1.
5. **Python standard library only.** No network at any point, in either phase.
6. **Deterministic.** The same puzzle must produce the same codeword in a fresh
   process. This is checked by encoding the corpus twice, in two processes, and
   comparing.
7. **No side channels.** Your codec must not write to the filesystem. The grader
   runs each phase in its own directory and fails the submission if any file is
   left behind that it did not create itself.

## How this is graded

On **10,000 held-out puzzles that are not in `data/train.txt`**. Requirements
1-7 are pass/fail gates; given those, the score is your `BITS`.

| codeword | pixels |  |
|---:|:--:|---|
| 144 bits | 6 | the article's scheme — the bar to beat |
| **108 bits or fewer** | 5 | **the target. This is what you are asked to reach.** |
| 96 bits or fewer | 4 | recorded if you reach it; see below |

**108 bits is known to be reachable.** A codec that hits it exactly has been
written and verified to round-trip all 49,151 puzzles in the catalogue. It uses
no lookup tables, no search, and no puzzle data — only arithmetic. You are not
being asked to find something unproven.

**96 bits is a stretch with no known solution.** It is measured and reported,
never required, and failing to reach it costs you nothing. It is in the table
so that you know the target is 108 and not secretly lower.

## What will not work

The catalogue of 17-clue Sudokus has only 49,151 known members, so an *index*
into it would be about 16 bits. That is not compression, it is a lookup table,
and it is ruled out by construction rather than by rule: the graded puzzles are
not in your corpus, and 64 KB cannot hold a catalogue — the puzzles alone need
more than 600 KB however they are stored.

Nor can a codec assign indices *as it goes* and look them up on the way back.
Encoding and decoding are separate processes, so a table built during encoding
does not exist during decoding, and the decode process is never given the
puzzles to build one from.

## Deliverable

`/app/submission/codec.py`, meeting requirements 1-7, with `BITS <= 108`.
