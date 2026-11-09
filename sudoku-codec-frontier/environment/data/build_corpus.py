"""Build the task corpus from Royle's 17-clue catalogue.

Royle's list is partially canonicalised -- the first clue in reading order is
digit '1' 6,820 times but '9' only 1,825 times. A codec trained on that would
be fitting an artefact of how the catalogue was built, not the structure of
Sudoku. Each puzzle therefore gets a random Sudoku isomorphism applied:
digit relabelling, row-within-band and column-within-stack permutation,
band and stack permutation, and optional transpose. All of these map valid
17-clue puzzles to valid 17-clue puzzles and preserve uniqueness of solution.
"""
import random, sys

SEED = 20261109

def iso(p, rnd):
    perm = list('123456789'); rnd.shuffle(perm)
    lab = {str(i + 1): perm[i] for i in range(9)}
    g = [[p[r * 9 + c] for c in range(9)] for r in range(9)]
    g = [[lab[x] if x != '0' else '0' for x in row] for row in g]
    bands = list(range(3)); rnd.shuffle(bands)
    g = [g[b * 3 + i] for b in bands for i in rnd.sample(range(3), 3)]
    stacks = list(range(3)); rnd.shuffle(stacks)
    order = [s * 3 + i for s in stacks for i in rnd.sample(range(3), 3)]
    g = [[row[i] for i in order] for row in g]
    if rnd.random() < 0.5:
        g = [list(x) for x in zip(*g)]
    return ''.join(''.join(r) for r in g)

def main(src, train_out, held_out):
    rnd = random.Random(SEED)
    puz = [l.strip() for l in open(src) if l.strip()]
    assert len(puz) == 49151, len(puz)
    out = [iso(p, rnd) for p in puz]
    for q in out:
        assert len(q) == 81 and sum(c != '0' for c in q) == 17
    assert len(set(out)) == len(out), "isomorphism collided"
    rnd.shuffle(out)
    held, train = out[:10000], out[10000:]
    open(train_out, 'w').write('\n'.join(train) + '\n')
    open(held_out, 'w').write('\n'.join(held) + '\n')
    print(f"train {len(train)}  heldout {len(held)}  disjoint="
          f"{not (set(train) & set(held))}")

if __name__ == '__main__':
    main(*sys.argv[1:])
