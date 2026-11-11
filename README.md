# trysac-pg-plan-explainer

Explain PostgreSQL `EXPLAIN ANALYZE` JSON plans offline: compute exclusive time per node, rank the slowest nodes, and surface common problems with stable machine-readable codes.

## Installation

```bash
pip install trysac-pg-plan-explainer
```

## Usage

```python
import json
from pg_plan_explainer import parse_plan, analyze, render

plan_json = """{"Plan": {"Node Type": "Seq Scan", "Relation Name": "t", "Actual Total Time": 1.2, "Actual Loops": 1}}"""
root = parse_plan(plan_json)
report = analyze(root)
print(render(report))
```

## CLI

```bash
python -m pg_plan_explainer plan.json
```
Exit codes: `0` no findings, `1` findings found, `2` usage or invalid input.

## Error handling

`PlanError` is raised with a stable `code`:

- `invalid_json` – input is not valid JSON
- `invalid_plan` – JSON shape missing `Plan`
- `input_too_large` – input exceeds the default 20 MiB limit
- `too_deep` – plan nesting deeper than 100 levels
- `too_many_nodes` – more than 100,000 plan nodes

## Security

See `docs/SECURITY.md` for the threat model.

## License

MIT
