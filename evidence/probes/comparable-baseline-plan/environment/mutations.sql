-- Two realistic failure patterns in the historical corpus. Both make a run
-- ineligible as a comparison peer, for different reasons, and each has to be
-- discovered separately.
BEGIN;

-- 1. Out-of-memory at the top of a concurrency sweep. The row exists and the
--    sweep as a whole is recorded, but this sub-run did not complete.
UPDATE benchmark_results SET status = 'failed', total_token_throughput = NULL,
       metrics = metrics || '{"error": "CUDA out of memory at concurrency ceiling"}'::jsonb
WHERE id IN (
  SELECT id FROM (
    SELECT id,
           row_number() OVER (PARTITION BY model_name, gpu_type, gpu_count, precision,
                                           input_tokens, output_tokens, workload_type, concurrency
                              ORDER BY run_id DESC, sub_run_index DESC) AS rn,
           count(*) OVER (PARTITION BY model_name, gpu_type, gpu_count, precision,
                                       input_tokens, output_tokens, workload_type, concurrency) AS grp,
           concurrency AS c
    FROM benchmark_results
    WHERE status = 'success' AND total_token_throughput IS NOT NULL
  ) t WHERE rn = 1 AND grp = 3 AND c >= 32
);

-- 2. The runner wrote its result row and then died before the metrics were
--    attached. Status still reads success; there is no throughput to compare.
--    Deliberately aimed at groups that mutation 1 did not touch, so that
--    checking status alone is not enough to find these.
UPDATE benchmark_results SET total_token_throughput = NULL
WHERE id IN (
  SELECT id FROM (
    SELECT id,
           row_number() OVER (PARTITION BY model_name, gpu_type, gpu_count, precision,
                                           input_tokens, output_tokens, workload_type, concurrency
                              ORDER BY run_id, sub_run_index) AS rn,
           count(*) OVER (PARTITION BY model_name, gpu_type, gpu_count, precision,
                                       input_tokens, output_tokens, workload_type, concurrency) AS grp,
           concurrency AS c
    FROM benchmark_results
    WHERE status = 'success' AND total_token_throughput IS NOT NULL
  ) t WHERE rn = 1 AND grp = 3 AND c < 32
);

COMMIT;
