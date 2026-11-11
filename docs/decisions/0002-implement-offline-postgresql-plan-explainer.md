# Implement offline PostgreSQL plan explainer

Status: accepted (generated, pending human review)

## Context

EXPLAIN ANALYZE JSON output is the primary tool for diagnosing slow queries, but its nested structure and per-loop timings obscure where time is actually spent. Developers often miss misestimated row counts or sorts spilling to disk.

## Decision

Build a dependency-free Python package that parses the JSON output, computes exclusive node timings iteratively, ranks hotspots, and reports six structured findings (P001-P006) with stable codes. The library is usable as a module and a CLI.

## Consequences

The package works offline in CI pipelines, provides machine-readable findings, and enforces strict limits on input size, depth, and node count. It intentionally does not execute queries or suggest indexes beyond naming filter expressions.
