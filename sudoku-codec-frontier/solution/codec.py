"""Oracle codec: 17-clue Sudoku in a fixed 108 bits.

Two observations the article's scheme leaves on the table.

1. The clue positions are an unordered SET, not a sequence. The article spends
   17 x 8 = 136 bits on them plus 8 separators; the set itself carries only
   log2 C(81,17) = 56.83 bits. Rank the set in the combinatorial number system
   and the positions cost 57 bits, not 144.

2. A clue's digit is not a free choice out of nine. Once the positions are
   known -- and the decoder knows them before it reads any digit -- each cell's
   digit must differ from every digit already placed in its row, column and
   box. Coding each digit against its live candidate list costs 49.4 bits on
   average instead of 17 x log2(9) = 53.9.

Both parts are folded into one mixed-radix integer so there is no per-field
rounding: only the final integer is padded to a whole number of bits.
"""
from math import comb

BITS = 108
C = comb(81, 17)

def _rank(cells):
    """colex rank of a sorted 17-subset of {0..80} -> [0, C(81,17))"""
    return sum(comb(c, k + 1) for k, c in enumerate(cells))

def _unrank(r):
    cells = []
    for k in range(16, -1, -1):
        c = k
        while comb(c + 1, k + 1) <= r:
            c += 1
        cells.append(c)
        r -= comb(c, k + 1)
    return cells[::-1]

def _cands(i, rows, cols, box):
    r, c = divmod(i, 9)
    used = rows[r] | cols[c] | box[(r // 3) * 3 + c // 3]
    return [d for d in '123456789' if d not in used]

def _place(i, ch, rows, cols, box):
    r, c = divmod(i, 9)
    rows[r].add(ch); cols[c].add(ch); box[(r // 3) * 3 + c // 3].add(ch)

def encode(puzzle: str) -> str:
    cells = [i for i, ch in enumerate(puzzle) if ch != '0']
    rows = [set() for _ in range(9)]; cols = [set() for _ in range(9)]
    box = [set() for _ in range(9)]
    steps = []
    for i in cells:
        cand = _cands(i, rows, cols, box)
        steps.append((len(cand), cand.index(puzzle[i])))
        _place(i, puzzle[i], rows, cols, box)
    v = 0
    for radix, idx in reversed(steps):      # reversed so decode pops forward
        v = v * radix + idx
    value = v * C + _rank(cells)
    bits = format(value, '0%db' % BITS)
    if len(bits) != BITS:
        raise OverflowError("codeword exceeds %d bits" % BITS)
    return bits

def decode(bits: str) -> str:
    value = int(bits[:BITS], 2)
    v, rank = divmod(value, C)
    cells = _unrank(rank)
    rows = [set() for _ in range(9)]; cols = [set() for _ in range(9)]
    box = [set() for _ in range(9)]
    grid = ['0'] * 81
    for i in cells:
        cand = _cands(i, rows, cols, box)
        v, idx = divmod(v, len(cand))
        grid[i] = cand[idx]
        _place(i, grid[i], rows, cols, box)
    return ''.join(grid)
