# Architecture

`pg_plan_explainer` is a single-package, stdlib-only Python library.

- **Parsing** (`parse_plan`): Accepts a JSON string from `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. It is decoded with `json.loads`, then a size check (`max_bytes` default 20 MiB) and an iterative tree walk enforce depth (100) and node count (100,000) limits. The walk is iterative, using an explicit stack, to avoid recursion limits on deep plans.
- **Analysis** (`analyze`): Performs an iterative postorder traversal. For each node, `total_ms = Actual Total Time * Actual Loops`; `exclusive_ms = total_ms - sum(children total_ms)`, clamped at zero and rounded to three decimals. Hotspots are the top `top` (default 5) nodes by exclusive time, ties broken by traversal order. Findings (`P001`–`P006`) are generated from PostgreSQL field semantics and sorted by traversal order then code.
- **Rendering / CLI**: `render` produces the human-readable output; `src/pg_plan_explainer/__main__.py` reads a file or stdin and maps findings to exit codes.

## Design decisions

- **Stdlib only**: No dependencies beyond Python ≥3.10; JSON parsing and dataclasses suffice.
- **Frozen dataclasses**: Public model types are immutable for safe sharing.
- **Logging**: A module logger with `NullHandler`; library users may configure logging.
- **Adversarial limits**: All untrusted inputs bound by size, depth, and node count.

See `docs/decisions/` for recorded decisions.
