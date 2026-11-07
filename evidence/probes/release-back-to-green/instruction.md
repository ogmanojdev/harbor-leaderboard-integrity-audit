# Get the release back to green

This container runs the AIStudio benchmarking backend: a FastAPI service and
worker in `/app/app`, its migration chain in `/app/alembic`, its test suite in
`/app/tests`, and a PostgreSQL database already populated with historical
benchmark runs.

A merge landed that should not have. **Three release gates are red**, and they
are red for unrelated reasons — fixing one will not fix the others.

## The gates

```bash
/app/gates.sh      # all three, with the state of each
```

Each gate also runs on its own:

```bash
pytest tests/      # SUITE — the service's own test suite
/app/e2e.sh        # LIVE  — ingest -> leaderboard against the real database
/app/chain.sh      # CHAIN — builds a database from the revisions alone
```

They tell you *which* stage failed, not *why*. Run them as often as you like;
they cost nothing. Expect to fix something, run them again, and find the next
thing.

Note that the gates observe different things. The suite builds its schema from
the ORM models into a scratch database. The live path runs against the real
database, which was built by the migration chain. A defect visible to one of
those is not necessarily visible to the others.

## Done means

`/app/gates.sh` prints `RELEASE GREEN`, and does so because the service works,
not because a check was weakened.

## Rules

- **Do not modify `/app/tests/`, `/app/e2e.sh`, `/app/chain.sh` or
  `/app/gates.sh`**, and do not change what any of them assert. Your work is
  graded by equivalent checks that are not in this container.
- Fix causes in the application source under `/app/app`, in the migration chain
  under `/app/alembic`, or both, as appropriate to each defect.
- **Schema changes belong in the migration chain.** A bare `ALTER TABLE` against
  the live database is not a fix: the chain has to build the same schema from
  nothing, and that is checked.
- Do not stub, mock or bypass the database. Ingested runs must genuinely be
  stored in PostgreSQL and genuinely be returned by the leaderboard route.
- Leave the historical rows intact. Deleting rows is not a fix.
- `/app/api_contract/API_CONTRACT.md` is the published contract for the REST
  surface. Where behaviour is ambiguous, it is the reference.

Write a short `/app/fixes.md` listing each defect you found, where it was, and
what you changed. One or two lines each.
