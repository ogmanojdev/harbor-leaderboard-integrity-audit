# Find the regression in twelve runs

Throughput on the cluster dropped for some configurations after last month's
driver rollout, and nobody knows which. One slow configuration is confirmed:

```
model=llama31-70b  gpu=h100  precision=fp8  tp=8  driver=570  chunked_prefill=0
```

It measures roughly 45% below what the same hardware used to deliver. Other
configurations appear unaffected, but the pattern has not been established.

## What you can do

`bench` runs one configuration on the cluster and reports its throughput:

```bash
bench run --model M --gpu G --precision P --tp N --driver D --chunked-prefill 0|1
bench budget
```

The configuration space:

| field | values |
|---|---|
| `model` | llama31-70b, llama33-70b, deepseek-r1-70b, qwen25-32b |
| `gpu` | h100, mi210, rtx5090, t4 |
| `precision` | bf16, fp8, fp16 |
| `tp` | 1, 2, 4, 8 |
| `driver` | 550, 560, 570 |
| `chunked_prefill` | 0, 1 |

That is 1152 configurations. **You have 450 GPU-minutes and each run costs 45**
— ten runs in total, for a space you cannot enumerate. Measurements are
stable: the same configuration always returns the same throughput, so repeating
one buys nothing and still costs 45 minutes.

When the budget is gone, `bench` refuses to run. There is no way to extend it.

## Deliverable

`/app/finding.json`, stating the condition under which a configuration is
affected:

```json
{
  "condition": {
    "all_of": [
      {"field": "precision", "op": "eq",  "value": "fp8"},
      {"field": "tp",        "op": "gte", "value": 4}
    ]
  },
  "evidence": "one sentence on how the runs support this"
}
```

- `all_of` is a list of clauses, all of which must hold for a configuration to
  be affected. Give the smallest set of clauses that is exactly right.
- `field` is one of the six above. `op` is one of `eq`, `ne`, `lt`, `lte`,
  `gt`, `gte`. `value` is a string for text fields and a number for `tp` and
  `chunked_prefill`.
- The example above is a **format illustration, not a hint**.

Your condition is applied to all 1152 configurations and compared against the
truth, so it must be right at the boundaries — not merely right about which
fields are involved.
