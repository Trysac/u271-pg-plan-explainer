# pg-plan-explainer

[![PyPI version](https://img.shields.io/pypi/v/trysac-pg-plan-explainer)](https://pypi.org/project/trysac-pg-plan-explainer/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-pg-plan-explainer)](LICENSE)
[![CI](https://github.com/Trysac/u271-pg-plan-explainer/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u271-pg-plan-explainer/actions/workflows/ci.yml)

Explain PostgreSQL EXPLAIN ANALYZE JSON plans: exclusive time per node, the slowest nodes, and findings for filter-heavy scans, misestimates, disk sorts, hash batches and costly nested loops

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-pg-plan-explainer
# or
uv add trysac-pg-plan-explainer
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import pg_plan_explainer

# normalize() trims surrounding whitespace and lower-cases the text.
print(pg_plan_explainer.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    pg_plan_explainer.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
