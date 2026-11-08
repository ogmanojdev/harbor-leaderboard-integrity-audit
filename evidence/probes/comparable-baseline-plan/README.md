# collinear-candidate/comparable-baseline-plan

Every benchmark **run** in a real corpus must reach a floor of three comparable
peers *other than itself*, within a budget of 23 sweeps. The comparability rule
and its peer-eligibility clause are **implemented and tested in the repository
rather than stated in the instruction**, and the provided `validate_plan.py`
checks structure only — deliberately not coverage, not eligibility, not the
budget.

```bash
harbor run -p ./comparable-baseline-plan -a oracle
harbor run -p ./comparable-baseline-plan -a claude -m opus-5-5
harbor view ./jobs
```

## Calibration

| solver | sweeps | coverage | budget | overall |
|---|---|---|---|---|
| oracle | 23 | pass | pass | **1.000** |
| counts every row, ignoring eligibility | 20 | fail — 19 configs short | pass | 0.50 |
| checks `status` but not the null metric | 23 | fail — 10 configs short | pass | 0.50 |
| counts correctly, one sweep per config | 174 | pass | fail | 0.70 |

Three wrong readings of the rule, three different failed dimensions. The third
row is the sharp one: the right *number* of sweeps and entirely the wrong 23.

## What the first trial changed

Trial 1 of this task scored **1.000** against a looser earlier spec (floor of
three runs per configuration, budget 14) — and in doing so it found two
ambiguities the author had not seen:

- `app/routers/results.py::_build_filter_conditions` drops any filter whose
  value is unset or zero, so the 16 corpus rows with a zero token count match
  every token setting through the REST path. "Comparable" was therefore
  undefined for those configurations.
- `comparable_results` excludes the target's own run, so a floor of three peers
  *per run* needs four eligible runs per configuration, not three. The earlier
  verifier counted three.

It then computed that 10 sweeps sufficed under the strict reading and spent the
remaining 4 of its 14 hedging both interpretations — using the author's budget
slack as insurance against the author's imprecision.

Both findings were verified against the source and both held. The spec is now
tightened: the floor is stated per run and excludes self, the listing-endpoint
disagreement is declared with the peer-matching logic named as authoritative,
and the budget is the true optimum (23), leaving no slack to hedge with.
