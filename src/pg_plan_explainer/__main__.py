from __future__ import annotations

import sys

from . import PlanError, analyze, parse_plan, render


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: python -m pg_plan_explainer <plan.json|->"""
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) != 1:
        print("usage: python -m pg_plan_explainer <plan.json|->", file=sys.stderr)
        return 2

    path = argv[0]
    try:
        if path == "-":
            text = sys.stdin.read()
        else:
            with open(path, encoding="utf-8") as f:
                text = f.read()
    except OSError as e:
        print(f"error: cannot read {path}: {e}", file=sys.stderr)
        return 2

    try:
        root = parse_plan(text)
    except PlanError as e:
        print(f"error: {e.code}", file=sys.stderr)
        return 2

    report = analyze(root)
    print(render(report))
    return 1 if report.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
