#!/usr/bin/env python3
"""Child process: runs ONE phase of the submitted codec and writes data only.

    runner.py encode <codec.py> <in: puzzles>   <out: BITS then codewords>
    runner.py decode <codec.py> <in: codewords> <out: puzzles>

Nothing here judges anything, and nothing it prints to stdout is read by the
grader -- results travel only through the output file, and every comparison is
made by the parent process, which never imports the codec.
"""
import importlib.util, sys


def load(path):
    spec = importlib.util.spec_from_file_location('submitted_codec', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    mode, codec_path, in_path, out_path = sys.argv[1:5]
    codec = load(codec_path)
    with open(in_path) as fh:
        lines = [l.strip() for l in fh if l.strip()]
    if mode == 'encode':
        out = [str(getattr(codec, 'BITS', -1))]
        out += [codec.encode(p) for p in lines]
    elif mode == 'decode':
        out = [codec.decode(b) for b in lines]
    else:
        raise SystemExit('unknown mode %r' % mode)
    with open(out_path, 'w') as fh:
        fh.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
