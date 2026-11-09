"""Reference implementation of the scheme from "Sudoku in six pixels"
(Pavan Tirumani, https://pavan.ink/sudoku-in-six-pixels).

For each digit 1..9 list the cell positions (0-80) holding it, in order.
Lay the nine lists end to end, separated by markers. Every position is written
as 7 bits with a leading '1'; every marker is a single '0'.

    17 positions x (1 + 7) bits  +  8 separators  =  144 bits  =  6 RGB pixels

The separator count is 8, not 9: nine groups need eight dividers between them.
That holds even when a digit is absent from the puzzle -- which is the common
case, not a corner case, since 48% of all 17-clue Sudokus use only 8 distinct
digits. The absent digit is simply an empty group: two adjacent '0' markers.
"""
BITS = 144

def encode(puzzle: str) -> str:
    groups = {d: [] for d in '123456789'}
    for i, ch in enumerate(puzzle):
        if ch != '0':
            groups[ch].append(i)
    out = []
    for n, d in enumerate('123456789'):
        for pos in groups[d]:
            out.append('1' + format(pos, '07b'))
        if n < 8:
            out.append('0')
    bits = ''.join(out)
    assert len(bits) == BITS, len(bits)
    return bits

def decode(bits: str) -> str:
    grid = ['0'] * 81
    digit, i, placed = 1, 0, 0
    # Stops after the 17th position, so trailing bits beyond the codeword are
    # never consulted.
    while placed < 17:
        if bits[i] == '1':
            pos = int(bits[i + 1:i + 8], 2)
            grid[pos] = str(digit)
            i += 8
            placed += 1
        else:
            digit += 1
            i += 1
    return ''.join(grid)
