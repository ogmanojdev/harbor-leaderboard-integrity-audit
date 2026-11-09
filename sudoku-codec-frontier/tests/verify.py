#!/usr/bin/env python3
"""Grade /app/submission/codec.py on the held-out 17-clue puzzles.

This process imports no part of the submission. The codec runs in four
short-lived children (see harness.py), each as `nobody`, each confined to its
own run directory, and every comparison is made here against puzzles the decode
children never receive.
"""
import json, os, sys, traceback

# The SCF_* overrides exist so this grader can be exercised on a laptop against
# deliberately-wrong codecs. The verifier container sets none of them --
# [verifier.env] in task.toml is empty.
TESTS_DIR = os.environ.get('SCF_TESTS_DIR', '/tests')
CORPUS = os.environ.get('SCF_HELDOUT', os.path.join(TESTS_DIR, 'data/heldout.txt'))
OUT_DIR = os.environ.get('SCF_OUT_DIR', '/logs/verifier')

sys.path.insert(0, TESTS_DIR)
from gates import (GATES, ARTICLE_BITS, TARGET_BITS, STRETCH_BITS,
                   MAX_SOURCE_BYTES)
from harness import run_codec

ARTIFACTS = os.environ.get('HARBOR_ARTIFACTS_DIR', '/logs/artifacts')

# Harbor reproduces an artifact's SOURCE path inside the verifier, so the file
# arrives at /app/submission/codec.py rather than under the artifacts dir.
CANDIDATES = [p for p in [os.environ.get('SCF_SUBMISSION')] if p] + [
    '/app/submission/codec.py',
    os.path.join(ARTIFACTS, 'submission/codec.py'),
    os.path.join(ARTIFACTS, 'codec.py'),
    '/submission/codec.py',
    '/logs/artifacts/app/submission/codec.py',
]

DIMS = ('losslessness', 'fixed_length', 'self_delimiting', 'determinism',
        'no_side_channel', 'size_limit', 'target_met')


def write(payload, report):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'reward.json'), 'w') as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    with open(os.path.join(OUT_DIR, 'report.txt'), 'w') as fh:
        fh.write(report.rstrip() + '\n')
    print(report)


def zero(reason, extra=''):
    payload = {d: 0.0 for d in DIMS}
    payload.update({'overall': 0.0, 'bits': 0.0, 'pixels': 0.0,
                    'compression_vs_article': 0.0, 'stretch_met': 0.0})
    write(payload, 'FAIL: %s\n%s' % (reason, extra))
    return 1


def main():
    found = next((p for p in CANDIDATES if os.path.isfile(p)), None)
    if not found:
        return zero('no submission found',
                    'searched:\n  ' + '\n  '.join(CANDIDATES))
    size = os.path.getsize(found)
    if size > MAX_SOURCE_BYTES:
        return zero('submission is %d bytes, limit is %d'
                    % (size, MAX_SOURCE_BYTES),
                    'A codec this large is not graded: the 64 KB limit exists '
                    'so a puzzle catalogue cannot be embedded.')

    puzzles = [l.strip() for l in open(CORPUS) if l.strip()]
    as_user = 'nobody' if os.geteuid() == 0 else None
    r = run_codec(found, puzzles, os.path.join(TESTS_DIR, 'runner.py'),
                  as_user=as_user)

    gates = {
        'losslessness': r.get('lossless', 0.0) * r.get('alphabet_ok', 0.0),
        'fixed_length': r.get('fixed_length', 0.0),
        'self_delimiting': r.get('self_delimiting', 0.0),
        'determinism': r.get('deterministic', 0.0),
        'no_side_channel': r.get('no_side_channel', 0.0),
        'size_limit': 1.0,
    }
    bits = r.get('bits', -1.0)
    valid = all(v == 1.0 for v in gates.values()) and bits > 0
    target_met = 1.0 if (valid and bits <= TARGET_BITS) else 0.0
    stretch_met = 1.0 if (valid and bits <= STRETCH_BITS) else 0.0

    if not valid:
        overall = 0.0
    elif bits <= TARGET_BITS:
        overall = 1.0
    elif bits < ARTICLE_BITS:
        overall = round(0.5 * (ARTICLE_BITS - bits)
                        / (ARTICLE_BITS - TARGET_BITS), 4)
    else:
        overall = 0.0

    payload = dict(gates)
    payload.update({
        'target_met': target_met, 'stretch_met': stretch_met,
        'bits': float(bits),
        'pixels': float(-(-int(bits) // 24)) if bits > 0 else 0.0,
        'compression_vs_article': round(ARTICLE_BITS / bits, 4) if bits > 0 else 0.0,
        'overall': overall,
    })

    lines = ['submission        %s (%d bytes)' % (found, size),
             'held-out puzzles  %d' % r.get('n', 0), '',
             'gates']
    for k in ('losslessness', 'fixed_length', 'self_delimiting', 'determinism',
              'no_side_channel', 'size_limit'):
        lines.append('  %-17s%s' % (k, 'pass' if gates[k] == 1.0 else 'FAIL'))
    if bits > 0:
        lines += ['', 'codeword          %d bits = %d pixels'
                  % (bits, payload['pixels']),
                  'article           %d bits (%.2fx)'
                  % (ARTICLE_BITS, payload['compression_vs_article']),
                  'target  <=%3d     %s' % (TARGET_BITS,
                                            'MET' if target_met else 'not met'),
                  'stretch <=%3d     %s' % (STRETCH_BITS,
                                            'MET' if stretch_met else 'not met (optional)')]
    lines += ['', 'overall           %.4f' % overall]
    if r.get('first_failure'):
        lines += ['', 'first failure     ' + r['first_failure']]
    write(payload, '\n'.join(lines))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(zero('verifier raised', traceback.format_exc()))
