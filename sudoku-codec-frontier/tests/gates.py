"""The gates, written once so the practice harness and the grader cannot drift.

A copy of this file is baked into the verifier image. Keep them identical.
"""
import random

PAD_SEED = 424242
MAX_SOURCE_BYTES = 64 * 1024
ARTICLE_BITS = 144
TARGET_BITS = 108
STRETCH_BITS = 96


def run_gates(codec, puzzles, pad_samples=2000):
    """Return a dict of gate outcomes and the measured codeword length."""
    declared = getattr(codec, 'BITS', None)
    res = {
        'n': len(puzzles),
        'declared_bits': declared if isinstance(declared, int) else -1,
        'lossless': 1.0, 'fixed_length': 1.0, 'self_delimiting': 1.0,
        'alphabet_ok': 1.0, 'bits': -1.0,
        'first_failure': '',
    }
    lengths = set()
    for p in puzzles:
        bits = codec.encode(p)
        if not isinstance(bits, str) or any(ch not in '01' for ch in bits):
            res['alphabet_ok'] = 0.0
            res['first_failure'] = 'encode returned a non-bitstring for ' + p
            return res
        lengths.add(len(bits))
        if codec.decode(bits) != p:
            res['lossless'] = 0.0
            res['first_failure'] = 'decode(encode(p)) != p for ' + p
            return res
    if len(lengths) != 1:
        res['fixed_length'] = 0.0
        res['first_failure'] = 'codeword length varies: %s' % sorted(lengths)
        return res
    measured = lengths.pop()
    res['bits'] = float(measured)
    if res['declared_bits'] != measured:
        res['fixed_length'] = 0.0
        res['first_failure'] = ('BITS is %r but encode emits %d'
                                % (declared, measured))
        return res

    # Nothing may ride in the length: the same codeword with arbitrary trailing
    # characters must still decode to the same puzzle.
    rnd = random.Random(PAD_SEED)
    for p in (puzzles if len(puzzles) <= pad_samples
              else rnd.sample(list(puzzles), pad_samples)):
        bits = codec.encode(p)
        for pad in ('0' * 24, '1' * 24,
                    ''.join(rnd.choice('01') for _ in range(24))):
            if codec.decode(bits + pad) != p:
                res['self_delimiting'] = 0.0
                res['first_failure'] = ('decode consumed past BITS for ' + p)
                return res
    return res
