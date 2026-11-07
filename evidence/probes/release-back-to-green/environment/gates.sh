#!/usr/bin/env bash
# Release gates. Runs all three and reports the state of each.
# Each gate tells you which stage failed, not why.
set -uo pipefail
S=0; L=0; C=0

echo "──────────── SUITE ────────────"
if pytest -q /app/tests/ >/tmp/g_suite.log 2>&1; then
  S=1; echo "SUITE: green — $(grep -oE '[0-9]+ passed' /tmp/g_suite.log | tail -1)"
else
  echo "SUITE: red — $(grep -oE '[0-9]+ failed[^,]*' /tmp/g_suite.log | tail -1 || echo 'collection failed')"
  grep -E '^FAILED' /tmp/g_suite.log | sed 's|FAILED /app/tests/test_services.py::||; s/ - .*//' | head -40
  echo "  (full output: /tmp/g_suite.log)"
fi

echo; echo "──────────── LIVE ─────────────"
if /app/e2e.sh >/tmp/g_live.log 2>&1; then
  L=1; echo "LIVE: green"
else
  echo "LIVE: red — $(grep -E '^STAGE [0-9]+: FAIL' /tmp/g_live.log | head -1)"
  echo "  (full output: /tmp/g_live.log)"
fi

echo; echo "──────────── CHAIN ────────────"
if /app/chain.sh >/tmp/g_chain.log 2>&1; then
  C=1; echo "CHAIN: green"
else
  echo "CHAIN: red — $(grep -E '^CHAIN [0-9]+: FAIL' /tmp/g_chain.log | head -1)"
  echo "  (full output: /tmp/g_chain.log)"
fi

echo; echo "═══════════════════════════════"
T=$((S+L+C))
echo "$T of 3 gates green"
[ "$T" = "3" ] && echo && echo "RELEASE GREEN"
