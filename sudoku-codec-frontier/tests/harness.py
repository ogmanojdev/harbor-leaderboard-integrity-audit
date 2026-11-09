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


def writable_roots(scratch):
    """Every directory the codec could write to while running as `nobody`.

    Setting TMPDIR is not a containment measure -- a codec can hardcode /tmp --
    so the surface is enumerated instead: the standard world-writable paths plus
    any other world-writable directory on the root filesystem.
    """
    roots = {scratch, '/tmp', '/var/tmp', '/dev/shm'}
    try:
        out = subprocess.run(
            ['find', '/', '-xdev', '-type', 'd', '-perm', '-0002',
             '-not', '-path', '/proc/*', '-not', '-path', '/sys/*'],
            capture_output=True, text=True, timeout=120).stdout
        roots.update(l for l in out.splitlines() if l.strip())
    except Exception:
        pass
    return sorted({r for r in roots if os.path.isdir(r)})


def _snapshot(roots):
    seen = set()
    for r in roots:
        seen |= _tree(r)
    return seen


def _purge(paths):
    """Delete anything the codec left behind, so state cannot reach the next
    phase even if the attribution above were somehow evaded."""
    for q in paths:
        try:
            os.remove(q)
        except Exception:
            shutil.rmtree(q, ignore_errors=True)


def _phase(runner, mode, codec, lines, scratch, as_user, label, roots):
    """Run one child process. Returns (output_lines, stray_files, stderr).

    Strays are computed across every writable root, not just the phase's own
    directory, and are deleted before the next phase runs.
    """
    run_dir = tempfile.mkdtemp(prefix='phase-%s-' % label, dir=scratch)
    inp = os.path.join(run_dir, 'in.txt')
    outp = os.path.join(run_dir, 'out.txt')
    with open(inp, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    open(outp, 'w').close()
    if as_user:
        os.chmod(run_dir, 0o777); os.chmod(inp, 0o444); os.chmod(outp, 0o666)
    expected = {inp, outp}
    before = _snapshot(roots)

    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': run_dir,
           'TMPDIR': run_dir, 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTHONPATH': ''}
    extra = {'user': as_user} if as_user else {}
    proc = subprocess.run([sys.executable, runner, mode, codec, inp, outp],
                          capture_output=True, text=True, cwd=run_dir,
                          env=env, timeout=PHASE_TIMEOUT, **extra)
    stray = sorted(_snapshot(roots) - before - expected)
    out_lines = None
    if proc.returncode == 0:
        with open(outp) as fh:
            out_lines = [l.rstrip('\n') for l in fh if l.strip() != '']
    err = (proc.stdout or '')[-1500:] + (proc.stderr or '')[-3000:]
    _purge(stray)
    shutil.rmtree(run_dir, ignore_errors=True)
    if out_lines is None:
        return None, stray, err
    return out_lines, stray, ''


def run_codec(codec_path, puzzles, runner_path, as_user=None, scratch=None):
    """Four isolated phases, then judge. Returns the gate dict."""
    own_scratch = scratch is None
    scratch = scratch or tempfile.mkdtemp(prefix='scf-')
    if as_user:
        os.chmod(scratch, 0o777)
    try:
        roots = writable_roots(scratch)
        strays, errs = [], []

        out_a, s, e = _phase(runner_path, 'encode', codec_path, puzzles,
                             scratch, as_user, 'enc-a', roots)
        strays += s; errs.append(e)
        if out_a is None:
            return _error('encode raised', errs[-1], len(puzzles), strays)
        # The child reports its module's BITS on the first line. Misreporting it
        # can only lose the fixed_length gate, since it is checked against the
        # codeword lengths this process measures.
        declared = int(out_a[0]) if out_a and out_a[0].lstrip('-').isdigit() else -1
        bits_a = out_a[1:]

        # Fresh process, so the second encode cannot see the first one's state.
        out_b, s, e = _phase(runner_path, 'encode', codec_path, puzzles,
                             scratch, as_user, 'enc-b', roots)
        strays += s; errs.append(e)
        if out_b is None:
            return _error('second encode raised', errs[-1], len(puzzles), strays)
        bits_b = out_b[1:]

        # Decode sees codewords only.
        dec, s, e = _phase(runner_path, 'decode', codec_path, bits_a,
                           scratch, as_user, 'dec', roots)
        strays += s; errs.append(e)
        if dec is None:
            return _error('decode raised', errs[-1], len(puzzles), strays)

        pad = pads()
        padded = [b + pad[i % len(pad)] for i, b in enumerate(bits_a)]
        decp, s, e = _phase(runner_path, 'decode', codec_path, padded,
                            scratch, as_user, 'dec-pad', roots)
        strays += s; errs.append(e)
        if decp is None:
            return _error('padded decode raised', errs[-1], len(puzzles), strays)

        note = ('codec wrote files outside its declared output: %s'
                % strays[:5]) if strays else ''
        return judge(puzzles, declared, bits_a, bits_b, dec, decp,
                     not strays, note)
    finally:
        if own_scratch:
            shutil.rmtree(scratch, ignore_errors=True)


def _error(what, detail, n, strays=()):
    from gates import GATES
    r = {g: 0.0 for g in GATES}
    note = ''
    if strays:
        note = ' (codec also wrote outside its output: %s)' % list(strays)[:3]
    r.update({'n': n, 'bits': -1.0,
              'first_failure': '%s: %s%s' % (what, detail, note)})
    return r
