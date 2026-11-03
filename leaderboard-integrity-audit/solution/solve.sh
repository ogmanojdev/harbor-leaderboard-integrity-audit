#!/bin/bash
# Oracle solution.
#
# Installs the validator into the location the task specifies, then derives both
# audit artifacts from the database. No result is hardcoded: the findings come
# from running the validator over records projected from the three tables, and
# the leaderboard is recomputed from the runs that survive the audit.
set -euo pipefail

install -D -m 0644 /solution/result_validator.py /app/app/services/result_validator.py

mkdir -p /app/audit
python3 /solution/audit.py

echo "--- findings"
head -c 400 /app/audit/findings.json; echo
echo "--- leaderboard"
head -c 400 /app/audit/leaderboard.json; echo
