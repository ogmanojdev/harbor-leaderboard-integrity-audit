#!/usr/bin/env python3
"""Score a codec the way the grader will, against the training corpus.

    python3 /app/reference/measure.py                  # scores /app/submission/codec.py
    python3 /app/reference/measure.py -n 5000          # faster, on a subset
    python3 /app/reference/measure.py path/to/codec.py

The held-out grading set is not in this container, so a good score here is
evidence and not a guarantee -- but every gate applied there is applied here.
"""
import argparse, importlib.util, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gates import (run_gates, ARTICLE_BITS, TARGET_BITS, STRETCH_BITS,
                   MAX_SOURCE_BYTES)

DEFAULT_CODEC = '/app/submission/codec.py'
DEFAULT_CORPUS = '/app/data/train.txt'


def load(path):
    spec = importlib.util.spec_from_file_location('submitted_codec', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    r = run_gates(load(a.codec), puzzles)

    print(f"codec        {a.codec}")
    print(f"source size  {size} bytes  (limit {MAX_SOURCE_BYTES}) "
          f"{'OK' if size <= MAX_SOURCE_BYTES else 'TOO LARGE'}")
    print(f"puzzles      {r['n']}")
    for g in ('alphabet_ok', 'lossless', 'fixed_length', 'self_delimiting'):
        print(f"{g:<13}{'pass' if r[g] == 1.0 else 'FAIL'}")
    if r['first_failure']:
        print(f"\nfirst failure: {r['first_failure']}")
        return 1
    bits = int(r['bits'])
    print(f"\ncodeword     {bits} bits = {-(-bits // 24)} pixels")
    print(f"vs article   {ARTICLE_BITS} bits "
          f"({ARTICLE_BITS / bits:.2f}x smaller)" if bits else "")
    print(f"target       {TARGET_BITS} bits  "
          f"{'MET' if bits <= TARGET_BITS else 'not met'}")
    print(f"stretch      {STRETCH_BITS} bits  "
          f"{'MET' if bits <= STRETCH_BITS else 'not met'} (optional)")
    return 0 if bits <= TARGET_BITS else 1


if __name__ == '__main__':
    sys.exit(main())
