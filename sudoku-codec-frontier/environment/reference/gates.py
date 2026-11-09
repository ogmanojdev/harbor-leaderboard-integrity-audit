"""Gate constants and the pure judging function.

This module never imports or executes a codec. Everything here operates on data
already produced by separate processes, so the grade is computed by a process
that has run none of the submitted code.

A copy is baked into the verifier image. Keep them identical.
"""
import random

PAD_SEED = 424242
MAX_SOURCE_BYTES = 64 * 1024
ARTICLE_BITS = 144
TARGET_BITS = 108
STRETCH_BITS = 96
PAD_WIDTH = 24

GATES = ('alphabet_ok', 'fixed_length', 'lossless', 'self_delimiting',
         'deterministic', 'no_side_channel')


def pads():
    """Three deterministic padding patterns appended to every codeword."""
    rnd = random.Random(PAD_SEED)
    return ('0' * PAD_WIDTH, '1' * PAD_WIDTH,
            ''.join(rnd.choice('01') for _ in range(PAD_WIDTH)))


def judge(puzzles, declared_bits, bits_a, bits_b, decoded, decoded_padded,
          side_channel_ok, notes):
    """Score phase outputs. All arguments are plain data.

    bits_a / bits_b  codewords from two independent encode processes
    decoded          puzzles from a decode process that saw only bits_a
    decoded_padded   same, but each codeword had padding appended
    """
    res = {g: 1.0 for g in GATES}
    res.update({'n': len(puzzles), 'bits': -1.0, 'first_failure': ''})

    def fail(gate, msg):
        res[gate] = 0.0
        if not res['first_failure']:
            res['first_failure'] = msg
        return res

    if not side_channel_ok:
        return fail('no_side_channel', notes or 'codec wrote to the filesystem')

    if len(bits_a) != len(puzzles):
        return fail('lossless', 'encode produced %d codewords for %d puzzles'
                    % (len(bits_a), len(puzzles)))

    for p, b in zip(puzzles, bits_a):
        if not b or any(ch not in '01' for ch in b):
            return fail('alphabet_ok', 'encode returned a non-bitstring for ' + p)

    lengths = {len(b) for b in bits_a}
    if len(lengths) != 1:
        return fail('fixed_length', 'codeword length varies: %s' % sorted(lengths))
    measured = lengths.pop()
    res['bits'] = float(measured)
    if declared_bits != measured:
        return fail('fixed_length', 'BITS is %r but encode emits %d'
                    % (declared_bits, measured))

    # Losslessness, judged here against puzzles the decode process never saw.
    if len(decoded) != len(puzzles):
        return fail('lossless', 'decode produced %d puzzles for %d codewords'
                    % (len(decoded), len(puzzles)))
    for p, q in zip(puzzles, decoded):
        if p != q:
            return fail('lossless', 'decode(encode(p)) != p for ' + p)

    # Nothing may ride in the length of a codeword.
    if len(decoded_padded) != len(puzzles):
        return fail('self_delimiting', 'padded decode produced %d of %d'
                    % (len(decoded_padded), len(puzzles)))
    for p, q in zip(puzzles, decoded_padded):
        if p != q:
            return fail('self_delimiting', 'decode consumed past BITS for ' + p)

    # Same input, same codeword, in a process that encoded nothing else first.
    if bits_a != bits_b:
        i = next(k for k in range(min(len(bits_a), len(bits_b)))
                 if bits_a[k] != bits_b[k])
        return fail('deterministic', 'encode is not deterministic for '
                    + puzzles[i])
    return res
