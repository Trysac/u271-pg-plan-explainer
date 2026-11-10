# Project record

## Objective

Explain PostgreSQL EXPLAIN ANALYZE JSON plans: exclusive time per node, the slowest nodes, and findings for filter-heavy scans, misestimates, disk sorts, hash batches and costly nested loops

## Scope

- In scope: the public API documented in [README.md](../README.md), typed and tested.
- Out of scope: anything that needs runtime dependencies or I/O without an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 703996 / 72073 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.1004 |

## Factory run u271 (measured from API usage)

| Date (UTC) | Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|---|
| 2026-11-10 | generation | deepseek-v4-pro | yes | 1952 | 20956 | 0 | 3328 | 0.0429 |
| 2026-11-10 | fix-1 | deepseek-flash | no | 9400 | 5519 | 0 | 40832 | 0.0048 |
| 2026-11-10 | fix-2 | deepseek-flash | no | 6682 | 667 | 0 | 12672 | 0.0014 |
| 2026-11-10 | audit | deepseek-flash | no | 31936 | 26693 | 0 | 438016 | 0.0221 |
| 2026-11-10 | fix-3 | deepseek-flash | no | 7810 | 2238 | 0 | 38144 | 0.0026 |
| 2026-11-10 | docs | deepseek-flash | no | 112968 | 16000 | 0 | 256 | 0.0265 |

Total: $0.1004. Prices: deepseek line, as measured by its adapter. Providers serve the current version of each model id, so the date tells which version answered; versions, launch stages and price sources per line are in the factory's model register (docs/MODELS.md).
