#!/bin/bash
# Verifier entrypoint.
#
# No `set -e`: the reward file must be written on every path, including when the
# checker itself fails. The checker also writes a zero reward from its own
# exception handler, so the reward exists even if this script is interrupted.
set -uo pipefail

mkdir -p /logs/verifier

python3 /tests/check_audit.py
EXIT=$?

if [ ! -s /logs/verifier/reward.json ]; then
  echo "checker produced no reward file; recording zero" >&2
  printf '{"overall": 0.0, "functional_correctness": 0.0, "constraint_satisfaction": 0.0, "robustness": 0.0, "artifact_quality": 0.0}\n' \
    > /logs/verifier/reward.json
fi

echo "verifier exit=${EXIT}"
cat /logs/verifier/reward.json
exit 0
