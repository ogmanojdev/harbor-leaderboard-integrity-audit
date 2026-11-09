"""Runs a codec in isolated phases and judges the results.

The codec is executed in four short-lived child processes -- two encode, two
decode -- so that no state can travel from encoding to decoding. The decode
processes receive codewords and nothing else: not the puzzles, not the corpus.
Every comparison is made by this process, which executes none of the codec.

Each child gets a private run directory as its cwd, HOME and TMPDIR, and is
expected to leave behind exactly the files this harness created. Anything else
it wrote is treated as an attempt to carry state between phases.
"""
import os, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gates import judge, pads

PHASE_TIMEOUT = 900


def _tree(root):
    out = set()
    for d, _, fs in os.walk(root):
        for f in fs:
            out.add(os.path.join(d, f))
    return out


def _phase(runner, mode, codec, lines, scratch, as_user, label):
    """Run one child process. Returns (output_lines, stray_files, stderr)."""
    run_dir = tempfile.mkdtemp(prefix='phase-%s-' % label, dir=scratch)
    inp = os.path.join(run_dir, 'in.txt')
    outp = os.path.join(run_dir, 'out.txt')
    with open(inp, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    open(outp, 'w').close()
    if as_user:
        os.chmod(run_dir, 0o777); os.chmod(inp, 0o444); os.chmod(outp, 0o666)
    expected = {inp, outp}

    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': run_dir,
           'TMPDIR': run_dir, 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTHONPATH': ''}
    extra = {'user': as_user} if as_user else {}
    proc = subprocess.run([sys.executable, runner, mode, codec, inp, outp],
                          capture_output=True, text=True, cwd=run_dir,
                          env=env, timeout=PHASE_TIMEOUT, **extra)
    stray = sorted(_tree(run_dir) - expected)
    if proc.returncode != 0:
        return None, stray, (proc.stdout or '')[-1500:] + (proc.stderr or '')[-3000:]
    with open(outp) as fh:
        lines_out = [l.rstrip('\n') for l in fh if l.strip() != '']
    shutil.rmtree(run_dir, ignore_errors=True)
    return lines_out, stray, ''


def run_codec(codec_path, puzzles, runner_path, as_user=None, scratch=None):
    """Four isolated phases, then judge. Returns the gate dict."""
    own_scratch = scratch is None
    scratch = scratch or tempfile.mkdtemp(prefix='scf-')
    if as_user:
        os.chmod(scratch, 0o777)
    try:
        strays, errs = [], []

        out_a, s, e = _phase(runner_path, 'encode', codec_path, puzzles,
                             scratch, as_user, 'enc-a')
        strays += s; errs.append(e)
        if out_a is None:
            return _error('encode raised', errs[-1], len(puzzles))
        # The child reports its module's BITS on the first line. Misreporting it
        # can only lose the fixed_length gate, since it is checked against the
        # codeword lengths this process measures.
        declared = int(out_a[0]) if out_a and out_a[0].lstrip('-').isdigit() else -1
        bits_a = out_a[1:]

        # Fresh process, so the second encode cannot see the first one's state.
        out_b, s, e = _phase(runner_path, 'encode', codec_path, puzzles,
                             scratch, as_user, 'enc-b')
        strays += s; errs.append(e)
        if out_b is None:
            return _error('second encode raised', errs[-1], len(puzzles))
        bits_b = out_b[1:]

        # Decode sees codewords only.
        dec, s, e = _phase(runner_path, 'decode', codec_path, bits_a,
                           scratch, as_user, 'dec')
        strays += s; errs.append(e)
        if dec is None:
            return _error('decode raised', errs[-1], len(puzzles))

        pad = pads()
        padded = [b + pad[i % len(pad)] for i, b in enumerate(bits_a)]
        decp, s, e = _phase(runner_path, 'decode', codec_path, padded,
                            scratch, as_user, 'dec-pad')
        strays += s; errs.append(e)
        if decp is None:
            return _error('padded decode raised', errs[-1], len(puzzles))

        note = ('codec wrote files outside its declared output: %s'
                % strays[:5]) if strays else ''
        return judge(puzzles, declared, bits_a, bits_b, dec, decp,
                     not strays, note)
    finally:
        if own_scratch:
            shutil.rmtree(scratch, ignore_errors=True)


def _error(what, detail, n):
    from gates import GATES
    r = {g: 0.0 for g in GATES}
    r.update({'n': n, 'bits': -1.0,
              'first_failure': '%s: %s' % (what, detail)})
    return r
