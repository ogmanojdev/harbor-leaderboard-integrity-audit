#!/usr/bin/env python3
"""Grade /app/submission/codec.py on the held-out 17-clue puzzles."""
import json, os, subprocess, sys, traceback

# The SCF_* overrides below exist so this grader can be exercised on a laptop
# against deliberately-wrong codecs. The verifier container sets none of them
# -- [verifier.env] in task.toml is empty -- so in a real run every path is the
# container path and nothing the agent does can reach them.
TESTS_DIR = os.environ.get('SCF_TESTS_DIR', '/tests')
CORPUS = os.environ.get('SCF_HELDOUT', os.path.join(TESTS_DIR, 'data/heldout.txt'))
OUT_DIR = os.environ.get('SCF_OUT_DIR', '/logs/verifier')

sys.path.insert(0, TESTS_DIR)
from gates import (ARTICLE_BITS, TARGET_BITS, STRETCH_BITS, MAX_SOURCE_BYTES)

ARTIFACTS = os.environ.get('HARBOR_ARTIFACTS_DIR', '/logs/artifacts')

# Harbor reproduces an artifact's SOURCE path inside the verifier, so the file
# arrives at /app/submission/codec.py rather than under the artifacts dir.
# Every plausible location is searched so a path change cannot silently zero a
# run.
CANDIDATES = [p for p in [os.environ.get('SCF_SUBMISSION')] if p] + [
    '/app/submission/codec.py',
    os.path.join(ARTIFACTS, 'submission/codec.py'),
    os.path.join(ARTIFACTS, 'codec.py'),
    '/submission/codec.py',
    '/logs/artifacts/app/submission/codec.py',
]

DIMENSIONS = ('losslessness', 'fixed_length', 'self_delimiting',
              'size_limit', 'target_met')


def write(payload, report):
    os.makedirs(OUT_DIR, exist_ok=True)
    # Written last, and only by this process: anything the submitted codec may
    # have done to this path while running is overwritten here.
    with open(os.path.join(OUT_DIR, 'reward.json'), 'w') as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    with open(os.path.join(OUT_DIR, 'report.txt'), 'w') as fh:
        fh.write(report.rstrip() + '\n')
    print(report)


def zero(reason, extra=''):
    payload = {d: 0.0 for d in DIMENSIONS}
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
                    'A codec this large is not being graded: the task allows '
                    '64 KB precisely so that a puzzle catalogue cannot be '
                    'embedded.')

    # Dropping to `nobody` needs root, which the verifier container has and a
    # laptop does not; the privilege drop is the only thing that varies.
    extra = {'user': 'nobody'} if os.geteuid() == 0 else {}
    proc = subprocess.run(
        [sys.executable, os.path.join(TESTS_DIR, 'runner.py'), found, CORPUS],
        capture_output=True, text=True, timeout=600,
        cwd='/tmp', env={**os.environ, 'SCF_TESTS_DIR': TESTS_DIR}, **extra,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return zero('the submitted codec raised while being measured',
                    (proc.stdout or '')[-2000:] + '\n'
                    + (proc.stderr or '')[-4000:])
    r = json.loads(proc.stdout.strip().splitlines()[-1])

    gates = {
        'losslessness': r['lossless'] * r['alphabet_ok'],
        'fixed_length': r['fixed_length'],
        'self_delimiting': r['self_delimiting'],
        'size_limit': 1.0,
    }
    bits = r['bits']
    valid = all(v == 1.0 for v in gates.values()) and bits > 0
    target_met = 1.0 if (valid and bits <= TARGET_BITS) else 0.0
    stretch_met = 1.0 if (valid and bits <= STRETCH_BITS) else 0.0

    if not valid:
        overall = 0.0
    elif bits <= TARGET_BITS:
        overall = 1.0
    elif bits < ARTICLE_BITS:
        # beat the article but missed the target: partial, scaled across the gap
        overall = round(0.5 * (ARTICLE_BITS - bits)
                        / (ARTICLE_BITS - TARGET_BITS), 4)
    else:
        overall = 0.0

    payload = dict(gates)
    payload.update({
        'target_met': target_met,
        'stretch_met': stretch_met,
        'bits': float(bits),
        'pixels': float(-(-int(bits) // 24)) if bits > 0 else 0.0,
        'compression_vs_article': round(ARTICLE_BITS / bits, 4) if bits else 0.0,
        'overall': overall,
    })

    lines = [
        'submission        %s (%d bytes)' % (found, size),
        'held-out puzzles  %d' % r['n'],
        '',
        'gates',
        '  losslessness     %s' % ('pass' if gates['losslessness'] else 'FAIL'),
        '  fixed_length     %s' % ('pass' if gates['fixed_length'] else 'FAIL'),
        '  self_delimiting  %s' % ('pass' if gates['self_delimiting'] else 'FAIL'),
        '  size_limit       pass',
        '',
        'codeword          %d bits = %d pixels' % (bits, payload['pixels']),
        'article           %d bits (%.2fx)' % (ARTICLE_BITS,
                                               payload['compression_vs_article']),
        'target  <=%3d     %s' % (TARGET_BITS, 'MET' if target_met else 'not met'),
        'stretch <=%3d     %s' % (STRETCH_BITS,
                                  'MET' if stretch_met else 'not met (optional)'),
        '',
        'overall           %.4f' % overall,
    ]
    if r['first_failure']:
        lines += ['', 'first failure     ' + r['first_failure']]
    write(payload, '\n'.join(lines))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(zero('verifier raised', traceback.format_exc()))
