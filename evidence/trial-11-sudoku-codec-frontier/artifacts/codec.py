"""17-clue Sudoku codec in 108 bits.

codeword = digit_value * C(81,17) + position_rank, as a 108-bit integer.
 - position_rank: rank of the 17-cell set in the combinatorial number system.
 - digit_value: mixed-radix number. Clues are visited in an adaptive order
   (most constrained cell first, ties -> lowest index), which the decoder can
   reproduce from the digits it has already decoded. Each clue's digit is
   coded among the digits not already used by placed peers (row/col/box).
"""
from math import comb

BITS = 108
_N = 17
_CP = comb(81, _N)

_PEERS = [[b for b in range(81) if b != a and (
    a // 9 == b // 9 or a % 9 == b % 9 or
    (a // 27 == b // 27 and a % 9 // 3 == b % 9 // 3))] for a in range(81)]


def _rank(pos):
    return sum(comb(c, k + 1) for k, c in enumerate(pos))


def _unrank(r):
    pos = []
    c = 80
    for k in range(_N, 0, -1):
        while comb(c, k) > r:
            c -= 1
        pos.append(c)
        r -= comb(c, k)
        c -= 1
    return pos[::-1]


def _next(rem, placed):
    best = None
    for i in sorted(rem):
        u = len({placed[j] for j in _PEERS[i] if j in placed})
        if best is None or u > best[0]:
            best = (u, i)
    i = best[1]
    used = {placed[j] for j in _PEERS[i] if j in placed}
    allowed = [d for d in range(1, 10) if d not in used]
    return i, allowed


def encode(puzzle):
    pos = [i for i in range(81) if puzzle[i] != '0']
    assert len(pos) == _N
    rem, placed = set(pos), {}
    digits = []  # (index, radix)
    while rem:
        i, allowed = _next(rem, placed)
        d = int(puzzle[i])
        digits.append((allowed.index(d), len(allowed)))
        placed[i] = d
        rem.discard(i)
    v = 0
    for idx, rad in reversed(digits):
        v = v * rad + idx
    total = v * _CP + _rank(pos)
    assert total < (1 << BITS)
    return format(total, '0%db' % BITS)


def decode(bits):
    total = int(bits[:BITS], 2)
    v, r = divmod(total, _CP)
    pos = _unrank(r)
    rem, placed = set(pos), {}
    while rem:
        i, allowed = _next(rem, placed)
        v, idx = divmod(v, len(allowed))
        placed[i] = allowed[idx]
        rem.discard(i)
    out = ['0'] * 81
    for i, d in placed.items():
        out[i] = str(d)
    return ''.join(out)
