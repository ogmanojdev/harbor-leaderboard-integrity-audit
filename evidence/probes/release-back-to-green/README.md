# release-back-to-green — the size probe (trial 8)

Not a submission and not a runnable task directory: the vendored application is
omitted, since it is public upstream and pinned by `environment/VENDORED_COMMIT`
(`corespan/aistudio-server` at `master`, Apache-2.0, authored by the submitter).
What is reproduced here is everything that constitutes the *design*:

| file | what it is |
|---|---|
| `instruction.md`, `task.toml` | the task as the agent receives it |
| `defects/plant.py` | the defect manifest — including the three classes rejected during calibration, kept with the reasons |
| `environment/gates.sh`, `e2e.sh`, `chain.sh` | the three gates the agent can run |
| `environment/verify.sh` | the independent graded probe, sharing no file with the above |
| `tests/check.py` | scoring, and the suite hash that makes tampering score zero |
| `solution/solve.sh` | the oracle |

The measurement this task was built to make is in
[`../../COST_SCALING.md`](../../COST_SCALING.md). Run log, reward and artifacts
are in `../trial-8-release-back-to-green/`.
