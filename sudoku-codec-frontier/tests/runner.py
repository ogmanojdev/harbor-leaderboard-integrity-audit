#!/usr/bin/env python3
"""Runs the SUBMITTED codec and prints one JSON line of gate results.

This is a separate process on purpose. Measuring a codec means executing code
the agent wrote, so it is executed here -- unprivileged, with its working
directory in /tmp -- and never inside the process that computes the grade.
"""
import importlib.util, json, os, sys
sys.path.insert(0, os.environ.get('SCF_TESTS_DIR', '/tests'))
from gates import run_gates

def main():
    codec_path, corpus_path = sys.argv[1], sys.argv[2]
    spec = importlib.util.spec_from_file_location('submitted_codec', codec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    puzzles = [l.strip() for l in open(corpus_path) if l.strip()]
    print(json.dumps(run_gates(mod, puzzles)))

if __name__ == '__main__':
    main()
