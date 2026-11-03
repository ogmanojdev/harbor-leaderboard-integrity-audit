-- Schema subset for the leaderboard-integrity-audit task.
--
-- Derived from the SQLAlchemy models in corespan/aistudio-server (Apache-2.0):
--   app/models/workload.py       -> workloads
--   app/models/node.py           -> nodes
--   app/models/task.py           -> tasks
--   app/models/task_log.py       -> task_logs
--   app/models/benchmark_result.py -> benchmark_results
--
-- This is a faithful subset, not the full upstream schema: columns not needed
-- by this task are omitted. Column names, types, constraints and comments that
-- ARE present match upstream, because the task turns on their exact semantics
-- (notably the uq_benchmark_run_sub constraint and the lowercase CHECKs).
--
-- The join path that matters:
--   benchmark_results.run_id = tasks.run_name
--   tasks.id                 = task_logs.task_id
-- There is no direct link from a log line to a result row.

CREATE TYPE workload_state AS ENUM (
    'CREATED', 'VALIDATING', 'VALIDATED', 'INSTALLING', 'READY', 'RUNNING', 'FAILED'
);

CREATE TYPE node_state AS ENUM (
    'ADDED', 'VALIDATING', 'VALIDATED', 'INSTALLING', 'READY', 'RUNNING', 'FAILED'
);

-- ── workloads ────────────────────────────────────────────────────────────────
CREATE TABLE workloads (
    id           UUID PRIMARY KEY,
    workload_id  VARCHAR(30)  NOT NULL UNIQUE,
    model_name   VARCHAR(128) NOT NULL,
    state        workload_state NOT NULL DEFAULT 'CREATED',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON COLUMN workloads.workload_id IS 'Human-readable ID returned to the UI as task_id.';

-- ── nodes ────────────────────────────────────────────────────────────────────
CREATE TABLE nodes (
    id           UUID PRIMARY KEY,
    workload_id  UUID NOT NULL REFERENCES workloads(id) ON DELETE CASCADE,
    machine_id   VARCHAR(30)  NOT NULL,
    machine_ip   VARCHAR(45)  NOT NULL,
    state        node_state   NOT NULL DEFAULT 'ADDED',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON COLUMN nodes.machine_id IS 'Short human-readable node identifier. e.g. ''node-a3f9bc''.';
CREATE INDEX ix_nodes_workload_id ON nodes (workload_id);

-- ── tasks ────────────────────────────────────────────────────────────────────
-- One row per benchmark execution. run_name is the bridge to benchmark_results.
CREATE TABLE tasks (
    id           UUID PRIMARY KEY,
    workload_id  UUID NOT NULL REFERENCES workloads(id) ON DELETE CASCADE,
    node_id      UUID REFERENCES nodes(id) ON DELETE SET NULL,
    run_name     VARCHAR(100) NOT NULL UNIQUE,
    task_config  JSONB NOT NULL DEFAULT '{}'::jsonb,
    status       VARCHAR(20)  NOT NULL DEFAULT 'running',
    started_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
COMMENT ON COLUMN tasks.run_name IS 'Human-readable run identifier. Also used as run_id in BenchmarkResult.';
COMMENT ON COLUMN tasks.task_config IS 'Exact benchmark config used for this run. Snapshot from workload_config.';
COMMENT ON COLUMN tasks.status IS 'Execution status: ''running'', ''success'', ''failed''.';
CREATE INDEX ix_tasks_workload_id ON tasks (workload_id);
CREATE INDEX ix_tasks_run_name ON tasks (run_name);

-- ── task_logs ────────────────────────────────────────────────────────────────
-- Append-only. One row per stdout/stderr line from the SSH session.
CREATE TABLE task_logs (
    id        UUID PRIMARY KEY,
    task_id   UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    line      TEXT NOT NULL,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON COLUMN task_logs.line IS 'Single log line from the SSH session stdout/stderr.';
CREATE INDEX ix_task_logs_task_id_logged_at ON task_logs (task_id, logged_at);

-- ── benchmark_results ────────────────────────────────────────────────────────
-- Two-layer storage: typed hot columns for leaderboard sorting, plus the full
-- raw runner payload in the metrics JSONB blob.
CREATE TABLE benchmark_results (
    id                     UUID PRIMARY KEY,
    run_id                 VARCHAR(64)  NOT NULL,
    sub_run_index          INTEGER      NOT NULL DEFAULT 0,
    model_name             VARCHAR(128) NOT NULL,
    pipeline_version       VARCHAR(128) NOT NULL,
    node_ips               TEXT[]       NOT NULL,
    gpu_type               VARCHAR(16)  NOT NULL,
    gpu_count              INTEGER      NOT NULL,
    gpu_model              VARCHAR(64),
    server_name            VARCHAR(128),
    precision              VARCHAR(16)  NOT NULL,
    input_tokens           INTEGER      NOT NULL,
    output_tokens          INTEGER      NOT NULL,
    concurrency            INTEGER      NOT NULL,
    parallelism            VARCHAR(16),
    workload_type          VARCHAR(32)  NOT NULL DEFAULT 'llm',
    status                 VARCHAR(16)  NOT NULL DEFAULT 'success',
    total_token_throughput DOUBLE PRECISION,
    mean_ttft_ms           DOUBLE PRECISION,
    mean_tpot_ms           DOUBLE PRECISION,
    mean_e2el_ms           DOUBLE PRECISION,
    metrics                JSONB        NOT NULL DEFAULT '{}'::jsonb,
    started_at             TIMESTAMPTZ  NOT NULL,
    completed_at           TIMESTAMPTZ,
    duration_seconds       DOUBLE PRECISION,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),

    -- A run_id + sub_run_index pair must be unique.
    -- ON CONFLICT on this pair = idempotent ingest (safe to POST twice).
    CONSTRAINT uq_benchmark_run_sub UNIQUE (run_id, sub_run_index),

    -- Enforce lowercase on classification fields, so the leaderboard dropdowns
    -- cannot acquire duplicates like 'A100' vs 'a100'.
    CONSTRAINT ck_model_name_lower    CHECK (model_name = lower(model_name)),
    CONSTRAINT ck_gpu_type_lower      CHECK (gpu_type = lower(gpu_type)),
    CONSTRAINT ck_precision_lower     CHECK (precision = lower(precision)),
    CONSTRAINT ck_workload_type_lower CHECK (workload_type = lower(workload_type))
);
COMMENT ON COLUMN benchmark_results.total_token_throughput IS
    'Total tokens/sec across all concurrent requests. Primary leaderboard sort key.';
COMMENT ON COLUMN benchmark_results.metrics IS
    'Full raw metrics payload from the runner. No schema enforced.';
CREATE INDEX ix_benchmark_results_run_id ON benchmark_results (run_id);
CREATE INDEX ix_benchmark_results_model_name ON benchmark_results (model_name);
CREATE INDEX ix_benchmark_results_gpu_type ON benchmark_results (gpu_type);
CREATE INDEX ix_benchmark_results_concurrency ON benchmark_results (concurrency);
CREATE INDEX ix_benchmark_results_parallelism ON benchmark_results (parallelism);
