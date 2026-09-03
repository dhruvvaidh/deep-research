# Benchmark metrics summary

## Method 1 — Context-store compression

- Median compression ratio (raw chars / summary chars): 2.0x
- Estimated cost avoided across all runs: $-0.5951 ($-0.0661/run, conservative floor)

## Method 2 — Parallel fan-out speedup

- Median speedup across 18 concurrent specialist clusters: 2.01x

## Method 3 — Iteration cost/quality tradeoff

| max_iterations | n_runs | mean tokens | mean cost (USD) | mean wall-clock (s) | mean confidence |
|---|---|---|---|---|---|
| 1 | 3 | 386240 | 0.1894 | 275.8 | 0.70 |
| 2 | 3 | 1027519 | 0.4631 | 635.2 | 0.68 |
| 3 | 3 | 1509859 | 0.6559 | 879.6 | 0.62 |