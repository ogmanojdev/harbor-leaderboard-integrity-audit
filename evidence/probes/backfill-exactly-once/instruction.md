# Backfill the archived benchmark runs

`/app/archive` holds archived benchmark runs exported from an older system.
They have to be re-ingested into the ledger using the `backfill` tool, which
processes **one run per invocation**:

```bash
backfill process <run_id>
backfill status
```

## What makes this delicate

**`backfill` is not idempotent.** Processing a run a second time records it a
second time — the ledger has no uniqueness constraint, because the loader it
replaces had none either. There is no undo. Every run must be processed
**exactly once**.

Not every file in `/app/archive` is a run. Some archives are continuations of
another run and must be merged into it rather than ingested on their own.

Some runs will be rejected with a diagnostic. Each rejection is recoverable
from that run's own archive — the launch arguments, the device list, the
companion file, or the point at which the records stop being readable. Read the
diagnostic, read the archive, and re-run with the flag it asks for.
`backfill process --help` lists the flags.

## Done means

```
distinct runs  : 150
ledger entries : 150
records        : 1182
grand total    : 1288996.01
```

`backfill status` reports the ledger's current state, so you can check your own
work as you go. A grand total above the target means something was ingested
more than once; below it means something is missing or was ingested with the
wrong remediation.

## Deliverable

The ledger at `/app/ledger.db` in exactly the state above, and a short
`/app/report.json`:

```json
{
  "runs_processed": 150,
  "remediated": {"missing_precision": 0, "ambiguous_gpu_count": 0,
                 "split_sweep": 0, "stale_schema": 0, "corrupt_tail": 0},
  "unverified": []
}
```

`remediated` counts the runs you had to pass each flag for. `unverified` lists
the `run_id`s you are **not** confident were ingested correctly — an empty list
is a claim that every one of the 150 is right. Claiming confidence you do not
have is worse than listing a run here.
