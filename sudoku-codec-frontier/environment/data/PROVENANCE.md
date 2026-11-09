# Corpus provenance

`train.txt` (39,151 puzzles) and the held-out grading set (10,000 puzzles, not
present in this image) are both derived from Gordon Royle's catalogue of
17-clue Sudokus — 49,151 puzzles, each with a unique solution and no two
isomorphic to one another. No 17-clue puzzle has been found since 2009, and
McGuire, Tugemann and Civario proved in 2012 that no 16-clue puzzle exists, so
17 is the true minimum and this catalogue is believed complete.

Source  : https://github.com/lakshayg/sudoku/releases/download/sudoku17/sudoku17.txt
sha256  : 71755fa5646701ae543b1435012492ec5b99f3d42b08da847e6d48d8b87676d7
Lines   : 49151 (each 81 chars, exactly 17 non-'0')

## Why the puzzles were transformed

Royle's catalogue is partially canonicalised, and the artefact is measurable:
the first clue in reading order is digit '1' in 6,820 puzzles but '9' in only
1,825. A codec tuned on the raw catalogue would be fitting how the list was
built rather than the structure of Sudoku, and would not transfer.

`build_corpus.py` therefore applies one random Sudoku isomorphism per puzzle
(digit relabelling; row-within-band, column-within-stack, band and stack
permutation; optional transpose) under a fixed seed, then shuffles and splits
10,000 off for grading. Every one of those operations maps a valid 17-clue
puzzle to a valid 17-clue puzzle and preserves uniqueness of the solution.
After the transform the first-clue digit is near-uniform (~5,400 each).

Reproduce with:

    python3 build_corpus.py sudoku17.txt train.txt heldout.txt
