#!/usr/bin/env python3
"""Score a codec the way the grader will, against the training corpus.

    python3 /app/reference/measure.py                 # scores /app/submission/codec.py
    python3 /app/reference/measure.py -n 2000         # faster, on a subset
    python3 /app/reference/measure.py path/to/codec.py

Your codec is run in four separate short-lived processes -- two encode, two
decode. The decode processes are given codewords and nothing else. This is
exactly how the grader runs it, so a codec that depends on state surviving from
encoding to decoding will fail here too.

The held-out grading set is not in this container, so a good score here is
evidence rather than a guarantee.
"""
import argparse, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness import run_codec
from gates import (GATES, ARTICLE_BITS, TARGET_BITS, STRETCH_BITS,
                   MAX_SOURCE_BYTES)

DEFAULT_CODEC = '/app/submission/codec.py'
DEFAULT_CORPUS = '/app/data/train.txt'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('codec', nargs='?', default=DEFAULT_CODEC)
    ap.add_argument('--corpus', default=DEFAULT_CORPUS)
    ap.add_argument('-n', type=int, default=0, help='use only the first N puzzles')
    a = ap.parse_args()

    size = os.path.getsize(a.codec)
    puzzles = [l.strip() for l in open(a.corpus) if l.strip()]
    if a.n:
        puzzles = puzzles[:a.n]
    r = run_codec(os.path.abspath(a.codec), puzzles,
                  os.path.join(HERE, 'runner.py'))

    print(f"codec        {a.codec}")
    print(f"source size  {size} bytes  (limit {MAX_SOURCE_BYTES}) "
          f"{'OK' if size <= MAX_SOURCE_BYTES else 'TOO LARGE'}")
    print(f"puzzles      {r['n']}")
    print()
    for g in GATES:
        print(f"  {g:<17}{'pass' if r.get(g) == 1.0 else 'FAIL'}")
    if r.get('first_failure'):
        print(f"\nfirst failure: {r['first_failure']}")
        return 1
    bits = int(r['bits'])
    print()
    print(f"codeword     {bits} bits = {-(-bits // 24)} pixels")
    print(f"vs article   {ARTICLE_BITS} bits ({ARTICLE_BITS / bits:.2f}x smaller)")
    print(f"target       {TARGET_BITS} bits  "
          f"{'MET' if bits <= TARGET_BITS else 'not met'}")
    print(f"stretch      {STRETCH_BITS} bits  "
          f"{'MET' if bits <= STRETCH_BITS else 'not met'} (optional)")
    return 0 if bits <= TARGET_BITS else 1


if __name__ == '__main__':
    sys.exit(main())
