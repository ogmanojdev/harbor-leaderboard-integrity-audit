# Run report — collinear-candidate/leaderboard-integrity-audit

## 1. The task

A GPU benchmark leaderboard is about to be published, and hardware purchasing
decisions will be made from it. Several of the runs behind it are not valid or
not comparable with one another, and nobody knows which. The agent must find
them, publish a corrected leaderboard, and patch the ingest validator so the
same defects cannot recur.

Three artifacts are required:

| Artifact | What it is |
|---|---|
| `/app/audit/findings.json` | per-run defects, from a published code vocabulary |
| `/app/audit/leaderboard.json` | the corrected leaderboard, computed by a published rule |
| `/app/app/services/result_validator.py` | `validate_runs(records)`, exercised against a corpus the agent never sees |

## 2. Why the defects are real rather than planted

This is the part of the design I care most about. The task contains no invented
corruption. Every defect is the natural output of a defaulting code path in the
real ingest endpoint, `app/routers/ingest.py`:

```python
"pipeline_version": payload.config.get("pipeline_version", "unknown"),
"gpu_count":        payload.config.get("gpu_count", 1),
"precision":        payload.config.get("precision", "fp16"),
"input_tokens":     payload.config.get("input_tokens", 0),
"output_tokens":    payload.config.get("output_tokens", 0),
```

Every one of those fields decides whether two benchmark results can be compared.
When a runner omits one, the default is recorded silently and the row looks
healthy afterwards:

- `parallelism` stays `NULL` when `metrics.parallelism` is absent, so a tp8 run
  and a tp4 run become indistinguishable.
- `precision` silently becomes `fp16`, so an fp8 run is mislabelled and looks
  implausibly fast.
- `gpu_count` silently becomes `1`, so per-GPU normalisation is wrong by 4-8x.
- `input_tokens` / `output_tokens` become `0`, leaving throughput unanchored.
- `on_conflict_do_update` keys on `(run_id, sub_run_index)`, so re-ingesting one
  logical run under a *new* `run_id` duplicates silently.

The upstream migration history corroborates that this was a recurring, real
problem: `add_parallelism_to_benchmark_results`, `add_run_recipe_to_benchmark_results`,
`add_server_name_to_benchmark_results` and `add_image_tag_to_workload_types` were
each added separately. Those columns exist because results kept turning out not
to be comparable.

**Economic viability.** Benchmark numbers drive hardware purchasing, capacity
planning and vendor selection. A leaderboard that silently compares an fp8 run
against fp16 runs, or divides an 8-GPU result by one, recommends the wrong
hardware at six or seven figures. The deliverable is the validation layer that
should have existed. Any team running an internal benchmark leaderboard has
this problem; most discover it the way the upstream migrations suggest it was
discovered here, one column at a time, after the fact.

## 3. The trap

`total_token_throughput` carries this comment upstream:

> Total tokens/sec across all concurrent requests. Primary leaderboard sort key.

So the obvious move — sort by it — is wrong, and the platform's own MCP tools
make the wrong move easy and comfortable:

- `throughput_compare` compares a run "against comparable past runs" using the
  **recorded** configuration, which is exactly what is corrupt. A run whose
  precision was defaulted to fp16 is compared against genuine fp16 runs and
  reported as a large improvement.
- `/api/v1/benchmarks` returns a derived `per_gpu_throughput_tok_s`, so the API
  propagates `defaulted_gpu_count` straight into a headline metric.
- `summary` reports dashboard totals over everything, defective runs included.

None of this was planted. It is what the real tools do with corrupt data.

## 4. Long-horizon structure

The task cannot be done in one step or from one file.

1. **Schema archaeology.** No foreign key connects a result row to a log line.
   `benchmark_results.run_id` equals `tasks.run_name`, and `tasks.id` equals
   `task_logs.task_id`. The MCP tool signature enforces this too: `get_task_logs`
   takes a workload id, not a `run_id`.
2. **Establish ground truth.** `tasks.task_config` records what was *requested*,
   as against what ingest *stored*. It is empty for roughly 30% of runs, which
   predate the snapshot feature, so intent must then be recovered from the
   launch arguments and declared sweep in `task_logs`.
3. **Enumerate six defect classes**, two of which are invisible per-row:
   a truncated sweep is a *count* against a declaration, and a duplicate is a
   cross-run fingerprint match.
4. **Avoid over-rejecting.** Three decoys trip naive heuristics while being
   genuinely valid.
5. **Recompute the leaderboard** under a published rule, excluding what failed.
6. **Generalise.** The validator is scored on a larger corpus the agent never
   sees, so nothing memorised survives.

## 5. Verifier design

Four independently scored dimensions in `reward.json`:

| Dimension | Weight | What it measures |
|---|---|---|
| `functional_correctness` | 0.40 | submitted validator's F1 on 65 unseen runs |
| `constraint_satisfaction` | 0.30 | corrected leaderboard, compared exactly |
| `robustness` | 0.20 | specificity on healthy runs, scaled by recall, times a determinism check |
| `artifact_quality` | 0.10 | findings over the local corpus, by F1 |

Design choices worth stating:

- **Standard library only.** The task is offline in both phases, so grading
  cannot depend on fetching a test dependency. No pytest, no `uvx`, no index.
  Nothing about a grade can turn on whether a mirror is up — the same failure
  mode the brief disqualifies, applied to the grader instead of the agent.
- **Separate verifier container.** The three declared artifacts are collected
  from the agent's container and uploaded into a fresh one, so a submission
  cannot tamper with grading.
- **Graded on typed data, never prose.** `evidence` strings are explicitly not
  scored. The defect vocabulary is published in `instruction.md`, so comparing
  codes is a documented enum rather than brittle string matching.
- **A vocabulary wider than the corpus.** Nine codes are published; six occur.
  Publishing exactly the six present would hand over the enumeration, which is
  half the task. The extra three also probe whether a model asserts defects it
  has not evidenced.
- **The reward file is written on every path**, including from the checker's own
  exception handler.

## 6. Calibration against deliberately bad solutions

Each strategy was run end-to-end, with artifacts regenerated per strategy:

| Strategy | overall | func | constraint | robust | artifact |
|---|---|---|---|---|---|
| Oracle, all six classes | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Do nothing | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Flag everything | 0.030 | 0.074 | 0.000 | 0.000 | 0.000 |
| Memorise the seed run ids | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Partial: 3 of 6 classes | 0.770 | 0.720 | 0.700 | 1.000 | 0.720 |
| Column diff only, never reads logs | 0.770 | 0.933 | 0.333 | 1.000 | 0.968 |

The last row is the designed difficulty lever working. Diffing `task_config`
against the recorded columns without ever reading `task_logs` detects 93% of
defects and still produces a badly wrong leaderboard, because the defective runs
whose config snapshot is empty survive the audit and corrupt the rankings.

Degenerate strategies collapse to ~0; plausible but incomplete ones land near
0.77; only a complete solution reaches 1.0.

## 7. Fairness audit

| Requirement | How it is met |
|---|---|
| Solvable | Oracle passes. Detection reproduced exactly on three independently seeded corpora: 16/16, no false positives. |
| Unambiguous | `instruction.md` publishes the defect vocabulary, the exact leaderboard rule, the validator signature and input schema, and every output path. |
| Substantive | Failure comes from incomplete inspection, missed enumeration and trusting a summary tool — not from tricks or formatting. |
| Reproducible | No network in either phase. Database seeded at image build. Dependencies installed with `--require-hashes`. Corpus committed. |
| Non-brittle | Grading compares typed values and numbers. No exact-string matching anywhere. |
| Not time-limited | Agent budget is 5400s, roughly 3x the oracle path. |
| No leaked solution | `tests/` and `solution/` are never copied into the image; the generator lives outside every image. |

### Two fairness bugs found during development, and fixed at the source

**A defect that was not one.** `missing_parallelism` was initially injected into
a single-GPU run. On a 1-GPU recipe a NULL `parallelism` has no comparability
consequence — `tp1` is the only possibility — so a correct validator would have
been punished for *not* flagging a harmless omission, while the single-GPU decoy
rewards exactly that restraint. The same observable would have been both
defective and valid depending on where it appeared. Injection is now restricted
to multi-GPU recipes.

**An ill-defined duplicate.** Both members of a duplicated pair were identical
apart from `run_id`, so "which copy is redundant" had no data-derivable answer,
and a `-retry` suffix made the class findable with one `grep`. Redeliveries now
get ordinary fresh identifiers and fire 37 minutes later, so the redundant copy
is well defined as the later-started member of a fingerprint-matched pair.

Both fixes went into the generator, not the detector. Changing the detector to
match a bad corpus would have hidden the ambiguity rather than removed it.

### A scoring flaw found by calibration

`robustness` was originally pure specificity, so a validator that flagged
nothing scored a perfect 1.0 for never having made a mistake — 0.20 of the
reward for doing nothing. Specificity is now scaled by held-out recall, so
restraint earns credit only when there is something to be restrained about.

## 8. Model runs

See section 9 for the target-model trial and failure analysis.

## 9. Limitations, stated plainly

- **`summary` drifts with wall-clock time.** It reports over a rolling
  `last_30d` window, so once real time moves past the seeded timestamps it
  returns fewer runs and eventually none. Nothing graded depends on it — the
  verifier is entirely time-independent — but the agent's view of that one tool
  is not stable across distant reruns. Shifting the corpus to build time would
  trade this for non-determinism between builds, which is worse.
- **`psql` remains available**, so an agent can bypass the MCP tools. Removing
  it would strengthen the MCP framing, but the list endpoint omits `parallelism`
  and the raw `metrics` blob, so an MCP-only agent could not observe a NULL
  `parallelism` column. Unsolvable is a worse failure than a redundant access
  path.
- **Metrics are synthetic.** Throughput figures come from a saturation curve,
  not from real hardware. Their absolute values carry no information; only the
  comparisons between them matter, and those are what the task turns on.
- **The signing key is committed.** It authenticates nothing outside the
  sandbox — there is no network, and the only server it addresses runs in the
  same container — and committing it is what makes the build reproducible.
- **One residual anti-cheat gap.** The verifier imports and executes the agent's
  own module, which is unavoidable for a patch-this-function task. It runs in a
  separate container, under a timeout, with the reward written on every path.

## 10. Provenance and licences

Created for this exercise. Not a port of SWE-bench, Terminal-Bench, a public
CTF, a Kaggle notebook, a public issue or a prior Collinear task.
`harbor init --include-canary-strings` stamped a canary GUID into the task files.

**New here:** the scenario, the corpus and its generator, the defect taxonomy,
the decoys, the verifier, the oracle, and all documentation.

**Vendored:** application source, database schema and MCP tool server from
[corespan/aistudio-server](https://github.com/corespan/aistudio-server),
Apache-2.0, authored by this submission's author, pinned at the commit in
`environment/VENDORED_COMMIT`. `LICENSE` and `NOTICE` ship alongside the code,
and `mcp-server/THIRD-PARTY-NOTICES.md` is retained.

No real benchmark data is used. Every run in the corpus is synthetic, and no IP
address, hostname or node identifier refers to real infrastructure.

## 11. Reproduction

```bash
harbor run -p ./leaderboard-integrity-audit -a oracle
harbor run -p ./leaderboard-integrity-audit -a claude -m opus-5-5
harbor view ./jobs
```

Static checks:

```bash
harbor lint  ./leaderboard-integrity-audit
harbor check ./leaderboard-integrity-audit
```

Regenerating the corpus (changes committed fixtures; both corpora must be
regenerated together):

```bash
python3 tools/gen_runs.py --seed 20261102 --runs 48 \
  --out-sql environment/seed/seed.sql \
  --out-truth tests/fixtures/seed_truth.json \
  --out-records tests/fixtures/seed_records.json

python3 tools/gen_runs.py --seed 777001 --runs 60 \
  --out-sql /dev/null \
  --out-truth tests/fixtures/heldout_truth.json \
  --out-records tests/fixtures/heldout_records.json
```
