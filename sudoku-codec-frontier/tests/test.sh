#!/bin/bash
# Verifier entrypoint. No `set -e`: a reward must be written on every path.
set -uo pipefail
mkdir -p /logs/verifier
python3 /tests/verify.py
EXIT=$?
if [ ! -s /logs/verifier/reward.json ]; then
  echo "checker produced no reward file; recording zero" >&2
  printf '{"overall": 0.0, "losslessness": 0.0, "fixed_length": 0.0, "self_delimiting": 0.0, "determinism": 0.0, "no_side_channel": 0.0, "size_limit": 0.0, "target_met": 0.0, "stretch_met": 0.0, "bits": 0.0, "pixels": 0.0, "compression_vs_article": 0.0}\n' \
    > /logs/verifier/reward.json
fi
echo "verifier exit=${EXIT}"
cat /logs/verifier/reward.json
exit 0
