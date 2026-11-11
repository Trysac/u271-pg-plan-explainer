from __future__ import annotations

import json
import sys

import pytest

from pg_plan_explainer import (
    Hotspot,
    PlanError,
    PlanRoot,
    __version__,
    analyze,
    parse_plan,
    render,
)
from pg_plan_explainer.__main__ import main


def sample_plan_dict() -> dict:
    return {
        "Plan": {
            "Node Type": "Hash Join",
            "Actual Total Time": 50.0,
            "Actual Loops": 1,
            "Plan Rows": 100,
            "Actual Rows": 120,
            "Plans": [
                {
                    "Node Type": "Seq Scan",
                    "Relation Name": "orders",
                    "Actual Total Time": 30.0,
                    "Actual Loops": 1,
                    "Plan Rows": 40,
                    "Actual Rows": 5000,
                    "Rows Removed by Filter": 95000,
                    "Filter": "(status = 'open'::text)",
                },
                {
                    "Node Type": "Hash",
                    "Actual Total Time": 15.0,
                    "Actual Loops": 1,
                    "Plan Rows": 200,
                    "Actual Rows": 200,
                    "Plans": [
                        {
                            "Node Type": "Seq Scan",
                            "Relation Name": "customers",
                            "Actual Total Time": 14.0,
                            "Actual Loops": 1,
                            "Plan Rows": 200,
                            "Actual Rows": 200,
                        }
                    ],
                },
            ],
        },
        "Planning Time": 0.2,
        "Execution Time": 52.3,
    }


def test_parse_plan_bare_object() -> None:
    plan_dict = sample_plan_dict()
    root = parse_plan(json.dumps(plan_dict))
    assert isinstance(root, PlanRoot)
    assert root.execution_ms == 52.3
    assert root.planning_ms == 0.2
    assert root.plan.node_type == "Hash Join"
    assert len(root.plan.children) == 2


def test_parse_plan_list() -> None:
    plan_dict = sample_plan_dict()
    root = parse_plan(json.dumps([plan_dict]))
    assert isinstance(root, PlanRoot)
    assert root.execution_ms == 52.3


def test_parse_plan_invalid_json() -> None:
    with pytest.raises(PlanError) as excinfo:
        parse_plan("not json")
    assert excinfo.value.code == "invalid_json"


def test_parse_plan_invalid_plan_no_plan() -> None:
    with pytest.raises(PlanError) as excinfo:
        parse_plan('{"foo": 1}')
    assert excinfo.value.code == "invalid_plan"


@pytest.mark.parametrize(
    "plans",
    [
        [42],
        "nope",
        None,
        {},
        [{"Node Type": "Result"}, "bad"],
    ],
)
def test_parse_plan_invalid_plans_shape(plans) -> None:
    plan = {"Node Type": "Result", "Plans": plans}
    with pytest.raises(PlanError) as excinfo:
        parse_plan(json.dumps({"Plan": plan}))
    assert excinfo.value.code == "invalid_plan"


def test_parse_plan_deep_nesting_does_not_crash() -> None:
    # Deeply nested plan beyond the interpreter recursion limit. Build the JSON
    # text directly: json.dumps recurses per nesting level (and on some Python
    # versions hits the recursion limit before the parser is ever exercised),
    # so serialising a deep dict would crash the test itself.
    depth = 500
    text = (
        '{"Plan": '
        + '{"Node Type": "Result", "Plans": [' * depth
        + '{"Node Type": "Result"}'
        + "]}" * depth
        + "}"
    )
    with pytest.raises(PlanError) as excinfo:
        parse_plan(text)
    assert excinfo.value.code == "too_deep"

    with pytest.raises(PlanError) as excinfo:
        parse_plan("[" * 5000)
    assert excinfo.value.code in ("too_deep", "invalid_json")


def test_parse_plan_input_too_large() -> None:
    text = " " * (20_971_521)
    with pytest.raises(PlanError) as excinfo:
        parse_plan(text)
    assert excinfo.value.code == "input_too_large"


def test_parse_plan_too_deep() -> None:
    # Build a plan nested 101 levels deep
    plan = {"Node Type": "Result"}
    current = plan
    for _ in range(100):
        child = {"Node Type": "Result"}
        current["Plans"] = [child]
        current = child
    root_dict = {"Plan": plan}
    with pytest.raises(PlanError) as excinfo:
        parse_plan(json.dumps(root_dict))
    assert excinfo.value.code == "too_deep"


def test_parse_plan_too_many_nodes() -> None:
    # Create a wide tree with >100000 nodes
    root = {"Node Type": "Result", "Plans": []}
    # Attach 100001 children
    children = []
    for _ in range(100_001):
        children.append({"Node Type": "Result"})
    root["Plans"] = children
    root_dict = {"Plan": root}
    with pytest.raises(PlanError) as excinfo:
        parse_plan(json.dumps(root_dict))
    assert excinfo.value.code == "too_many_nodes"


def test_analyze_example_hotspots_and_execution() -> None:
    root = parse_plan(json.dumps(sample_plan_dict()))
    report = analyze(root)
    assert report.execution_ms == 52.3
    assert report.analyzed is True
    assert report.hotspots[:3] == (
        Hotspot(node="Seq Scan on orders", exclusive_ms=30.0),
        Hotspot(node="Seq Scan on customers", exclusive_ms=14.0),
        Hotspot(node="Hash Join", exclusive_ms=5.0),
    )


def test_analyze_example_findings_codes_and_messages() -> None:
    root = parse_plan(json.dumps(sample_plan_dict()))
    report = analyze(root)
    codes = [f.code for f in report.findings]
    assert codes == ["P001", "P002"]
    p001 = next(f for f in report.findings if f.code == "P001")
    p002 = next(f for f in report.findings if f.code == "P002")
    assert (
        p001.message
        == "Seq Scan on orders removed 95000 rows by filter to return 5000; consider an index for (status = 'open'::text)"
    )
    assert p002.message == "Seq Scan on orders estimated 40 rows but returned 5000 (125.0x)"


def test_exclusive_time_multiplication_and_clamp() -> None:
    plan = {
        "Plan": {
            "Node Type": "Nested Loop",
            "Actual Total Time": 0.5,
            "Actual Loops": 1000,
            "Plans": [
                {
                    "Node Type": "Seq Scan",
                    "Relation Name": "a",
                    "Actual Total Time": 0.2,
                    "Actual Loops": 1000,
                }
            ],
        }
    }
    root = parse_plan(json.dumps(plan))
    report = analyze(root)
    # Parent total = 0.5*1000 = 500, child total = 0.2*1000 = 200, exclusive = 300
    parent_hotspot = next(h for h in report.hotspots if h.node == "Nested Loop")
    assert parent_hotspot.exclusive_ms == 300.0
    # Now cause negative exclusive (child total > parent total)
    plan["Plan"]["Actual Total Time"] = 0.1
    root = parse_plan(json.dumps(plan))
    report = analyze(root)
    parent_hotspot = next(h for h in report.hotspots if h.node == "Nested Loop")
    assert parent_hotspot.exclusive_ms == 0.0


def test_findings_p003_p004_p005_p006() -> None:
    plan = {
        "Plan": {
            "Node Type": "Sort",
            "Sort Space Type": "Disk",
            "Sort Space Used": 20480,
            "Actual Total Time": 1.0,
            "Actual Loops": 1,
            "Plans": [
                {
                    "Node Type": "Hash",
                    "Hash Batches": 8,
                    "Actual Total Time": 0.5,
                    "Actual Loops": 1,
                    "Plans": [
                        {
                            "Node Type": "Nested Loop",
                            "Actual Total Time": 0.4,
                            "Actual Loops": 1,
                            "Plans": [
                                {
                                    "Node Type": "Seq Scan",
                                    "Relation Name": "a",
                                    "Actual Total Time": 0.1,
                                    "Actual Loops": 1,
                                },
                                {
                                    "Node Type": "Index Scan",
                                    "Relation Name": "b",
                                    "Actual Total Time": 0.2,
                                    "Actual Loops": 5000,
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    }
    root = parse_plan(json.dumps(plan))
    report = analyze(root)
    codes = {f.code for f in report.findings}
    assert "P003" in codes
    assert "P004" in codes
    assert "P005" in codes
    # P006: add Temp Written Blocks to root
    plan["Plan"]["Temp Written Blocks"] = 120
    root = parse_plan(json.dumps(plan))
    report = analyze(root)
    p006 = next((f for f in report.findings if f.code == "P006"), None)
    assert p006 is not None
    assert p006.message == "Sort wrote 120 temp blocks"
    p003 = next(f for f in report.findings if f.code == "P003")
    assert "work_mem" in p003.message


def test_p003_message_uses_sort_space_used() -> None:
    plan = {
        "Plan": {
            "Node Type": "Sort",
            "Sort Space Type": "Disk",
            "Sort Space Used": 20480,
            "Actual Total Time": 1.0,
            "Actual Loops": 1,
        }
    }
    root = parse_plan(json.dumps(plan))
    report = analyze(root)
    p003 = next(f for f in report.findings if f.code == "P003")
    assert p003.message == "Sort on disk used 20480 kB; consider raising work_mem"


def test_plan_without_analyze() -> None:
    plan = {
        "Node Type": "Seq Scan",
        "Relation Name": "t",
        "Plan Rows": 100,
    }
    root = parse_plan(json.dumps({"Plan": plan}))
    report = analyze(root)
    assert report.analyzed is False
    assert report.hotspots == ()
    assert all(f.code not in ("P001", "P002", "P005") for f in report.findings)


def test_edge_cases() -> None:
    # Execution Time missing
    root = parse_plan(json.dumps({"Plan": {"Node Type": "Result"}}))
    assert root.execution_ms is None
    # CTE Scan without relation
    plan = {
        "Node Type": "CTE Scan",
        "Actual Total Time": 1.0,
        "Actual Loops": 1,
    }
    root = parse_plan(json.dumps({"Plan": plan}))
    report = analyze(root)
    assert all(h.node == "CTE Scan" for h in report.hotspots)
    # Actual Rows 0, Plan Rows 1 -> no P002
    plan = {
        "Node Type": "Seq Scan",
        "Relation Name": "t",
        "Actual Rows": 0,
        "Plan Rows": 1,
        "Actual Total Time": 0.0,
        "Actual Loops": 1,
    }
    root = parse_plan(json.dumps({"Plan": plan}))
    report = analyze(root)
    assert not any(f.code == "P002" for f in report.findings)
    # Actual Loops 0 -> exclusive 0.0
    plan = {
        "Node Type": "Nested Loop",
        "Actual Total Time": 1.0,
        "Actual Loops": 0,
        "Plans": [
            {
                "Node Type": "Seq Scan",
                "Relation Name": "a",
                "Actual Total Time": 0.5,
                "Actual Loops": 0,
            },
            {
                "Node Type": "Seq Scan",
                "Relation Name": "b",
                "Actual Total Time": 0.6,
                "Actual Loops": 0,
            },
        ],
    }
    root = parse_plan(json.dumps({"Plan": plan}))
    report = analyze(root)
    parent = next(h for h in report.hotspots if h.node == "Nested Loop")
    assert parent.exclusive_ms == 0.0


def test_render_with_findings() -> None:
    root = parse_plan(json.dumps(sample_plan_dict()))
    report = analyze(root)
    text = render(report)
    lines = text.split("\n")
    assert lines[0] == "Execution 52.3 ms"
    assert lines[1] == ""
    assert lines[2] == "Hotspots:"
    assert lines[3] == "30.0 ms  Seq Scan on orders"
    findings_index = lines.index("Findings:")
    assert lines[findings_index - 1] == ""
    assert lines[findings_index + 1].startswith("high P001 ")


def test_render_without_findings_or_execution() -> None:
    plan = {"Node Type": "Result"}
    root = parse_plan(json.dumps({"Plan": plan}))
    report = analyze(root)
    text = render(report)
    lines = text.split("\n")
    assert lines[0] == "Hotspots:"
    assert lines[1] == ""
    assert lines[2] == "Findings: none"


def test_cli_success_no_findings(tmp_path, capsys, monkeypatch) -> None:
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps({"Plan": {"Node Type": "Result"}}))
    monkeypatch.setattr(sys, "argv", ["pg_plan_explainer", str(plan_file)])
    exit_code = main([str(plan_file)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Findings: none" in captured.out


def test_cli_success_with_findings(tmp_path, capsys, monkeypatch) -> None:
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(sample_plan_dict()))
    monkeypatch.setattr(sys, "argv", ["pg_plan_explainer", str(plan_file)])
    exit_code = main([str(plan_file)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "P001" in captured.out


def test_cli_invalid_input(tmp_path, capsys, monkeypatch) -> None:
    exit_code = main([])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "usage" in captured.err


def test_cli_invalid_plan(tmp_path, capsys) -> None:
    plan_file = tmp_path / "bad.json"
    plan_file.write_text("not json")
    exit_code = main([str(plan_file)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "invalid_json" in captured.err


def test_version() -> None:
    assert __version__ == "0.1.0"
