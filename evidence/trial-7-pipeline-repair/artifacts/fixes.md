# Ingest → leaderboard pipeline fixes

1. **Wrong async DB driver** — `app/config.py` `get_database_url()` used `postgresql+psycopg_async://`, but psycopg (v3) isn't installed in the API venv (asyncpg is), so the app crashed on import. Changed it to `postgresql+asyncpg://`.
2. **Schema drift: missing `benchmark_results.mean_e2el_ms`** — the model and ingest both use this column, but the DB never got it, so the leaderboard SELECT returned 500. Ran `ALTER TABLE benchmark_results ADD COLUMN mean_e2el_ms double precision` and backfilled it from each row's `metrics->>'mean_e2el_ms'`. No other historical data was changed.
3. **Wrong ON CONFLICT target** — `app/routers/ingest.py` upserted on `(run_id)`, but the only unique constraint is `uq_benchmark_run_sub (run_id, sub_run_index)`, so every insert failed. Changed `index_elements` to `["run_id", "sub_run_index"]`.
4. **Ingested runs hidden from the leaderboard** — ingest stored `server_name = NULL` when the payload had no vendor, and the leaderboard filters out `server_name IS NULL`. Ingest now falls back to `payload.node_ip`, the same fallback NodeInspector and worker.py use.
5. **Hardening (not hit by the check)** — ingest now lowercases and strips `workload.name` so a mixed-case model name can't break `ck_model_name_lower` with a 500.

## Not fixed, outside the ingest path
`nodes` and `workloads` are well behind their models: `nodes` is missing columns such as `specs`, `gpus`, `machine_username` and `updated_at`; `workloads` is missing `workload_config`, `created_by`, `error_message` and `updated_at`; the `workload_events` table doesn't exist. The `/benchmarks/start` and Celery orchestration path will fail until those are migrated.
