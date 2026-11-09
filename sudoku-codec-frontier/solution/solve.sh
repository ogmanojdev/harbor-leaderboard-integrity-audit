#!/bin/bash
# Oracle solution.
#
# Installs the 108-bit codec and scores it with the same harness the agent has,
# so an oracle run exercises the real measurement path rather than asserting a
# result.
set -euo pipefail

install -D -m 0644 /solution/codec.py /app/submission/codec.py
python3 /app/reference/measure.py
