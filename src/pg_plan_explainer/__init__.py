from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

__all__ = [
    "Finding",
    "Hotspot",
    "PlanError",
    "PlanNode",
    "PlanRoot",
    "Report",
    "__version__",
    "analyze",
    "parse_plan",
    "render",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class PlanError(Exception):
    """Base error for plan parsing and analysis."""

    code: Literal["invalid_json", "invalid_plan", "input_too_large", "too_deep", "too_many_nodes"]

    def __init__(
        self,
        code: Literal[
            "invalid_json", "invalid_plan", "input_too_large", "too_deep", "too_many_nodes"
        ],
    ) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PlanNode:
    node_type: str
    relation: str | None
    fields: Mapping[str, Any]
    children: tuple[PlanNode, ...] = ()


@dataclass(frozen=True)
class PlanRoot:
    plan: PlanNode
    planning_ms: float | None
    execution_ms: float | None


@dataclass(frozen=True)
class Hotspot:
    node: str
    exclusive_ms: float


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Literal["high", "medium", "low"]
    node: str
    message: str


@dataclass(frozen=True)
class Report:
    analyzed: bool
    execution_ms: float | None
    hotspots: tuple[Hotspot, ...]
    findings: tuple[Finding, ...]


def _label(node: PlanNode) -> str:
    return f"{node.node_type} on {node.relation}" if node.relation else node.node_type


def _parse_plan_tree(raw_plan: Mapping[str, Any], *, max_depth: int, max_nodes: int) -> PlanNode:
    """Build a PlanNode tree from JSON-decoded dict, iteratively, with limits."""
    stack1: list[tuple[Mapping[str, Any], int]] = [(raw_plan, 1)]
    stack2: list[tuple[Mapping[str, Any], int, list[Any]]] = []
    node_count = 0

    while stack1:
        raw, depth = stack1.pop()
        node_count += 1
        if node_count > max_nodes:
            raise PlanError("too_many_nodes")
        if depth > max_depth:
            raise PlanError("too_deep")
        children_raw = raw.get("Plans", [])
        if not isinstance(children_raw, list):
            raise PlanError("invalid_plan")
        for child in children_raw:
            if not isinstance(child, dict):
                raise PlanError("invalid_plan")
        stack2.append((raw, depth, children_raw))
        for child in children_raw:
            stack1.append((child, depth + 1))

    id_to_node: dict[int, PlanNode] = {}
    while stack2:
        raw, _, children_raw = stack2.pop()
        node_type = raw.get("Node Type")
        if not isinstance(node_type, str) or not node_type:
            raise PlanError("invalid_plan")
        relation = raw.get("Relation Name")
        if not isinstance(relation, str):
            relation = None
        children_nodes: list[PlanNode] = []
        for child_raw in children_raw:
            child_node = id_to_node.get(id(child_raw))
            if child_node is None:
                raise PlanError("invalid_plan")
            children_nodes.append(child_node)
        fields = {k: v for k, v in raw.items() if k not in ("Node Type", "Relation Name", "Plans")}
        node = PlanNode(
            node_type=node_type,
            relation=relation,
            fields=fields,
            children=tuple(children_nodes),
        )
        id_to_node[id(raw)] = node

    root_node = id_to_node.get(id(raw_plan))
    if root_node is None:
        raise PlanError("invalid_plan")
    return root_node


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_plan(text: str, *, max_bytes: int = 20_971_520) -> PlanRoot:
    """Parse EXPLAIN JSON output into a PlanRoot.

    Accepts a bare object or a one-element list containing the object.
    Raises PlanError with codes for invalid JSON, wrong shape, size limit,
    depth limit, or node count limit.
    """
    if len(text.encode("utf-8")) > max_bytes:
        raise PlanError("input_too_large")

    try:
        data = json.loads(text)
    except RecursionError:
        raise PlanError("too_deep") from None
    except ValueError:
        raise PlanError("invalid_json") from None

    container: Any = None
    if isinstance(data, dict):
        container = data
    elif isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        container = data[0]
    else:
        raise PlanError("invalid_plan")

    if "Plan" not in container or not isinstance(container["Plan"], dict):
        raise PlanError("invalid_plan")

    raw_plan = container["Plan"]
    planning_ms = _to_float(container.get("Planning Time"))
    execution_ms = _to_float(container.get("Execution Time"))
    plan_node = _parse_plan_tree(raw_plan, max_depth=100, max_nodes=100_000)
    return PlanRoot(plan=plan_node, planning_ms=planning_ms, execution_ms=execution_ms)


def _num(fields: Mapping[str, Any], key: str, default: float | None = None) -> float | None:
    v = fields.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(fields: Mapping[str, Any], key: str, default: int | None = None) -> int | None:
    v = fields.get(key)
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _node_findings(node: PlanNode) -> list[Finding]:
    findings: list[Finding] = []
    label = _label(node)
    fields = node.fields

    # P001
    if node.node_type == "Seq Scan" and node.relation:
        actual_rows = _int(fields, "Actual Rows")
        removed = _int(fields, "Rows Removed by Filter")
        loops = _int(fields, "Actual Loops")
        if (
            actual_rows is not None
            and removed is not None
            and loops is not None
            and removed > 10 * actual_rows
            and removed * loops > 1000
        ):
            filter_text = fields.get("Filter", "")
            if not isinstance(filter_text, str):
                filter_text = str(filter_text)
            if len(filter_text) > 200:
                filter_text = filter_text[:200]
            message = (
                f"Seq Scan on {node.relation} removed {removed} rows by filter "
                f"to return {actual_rows}; consider an index for {filter_text}"
            )
            findings.append(Finding("P001", "high", label, message))

    # P002
    if "Actual Rows" in fields and "Plan Rows" in fields:
        actual = _num(fields, "Actual Rows")
        plan = _num(fields, "Plan Rows")
        if actual is not None and plan is not None:
            maxv = max(actual, plan)
            minv = max(min(actual, plan), 1)
            ratio = maxv / minv
            if ratio > 10:
                message = f"{label} estimated {plan:g} rows but returned {actual:g} ({ratio:.1f}x)"
                findings.append(Finding("P002", "medium", label, message))

    # P003
    if node.node_type == "Sort" and fields.get("Sort Space Type") == "Disk":
        sort_space_used = fields.get("Sort Space Used")
        message = f"Sort on disk used {sort_space_used} kB; consider raising work_mem"
        findings.append(Finding("P003", "medium", label, message))

    # P004
    hash_batches = fields.get("Hash Batches")
    if hash_batches is not None:
        try:
            batches = int(hash_batches)
        except (TypeError, ValueError):
            batches = 0
        if batches > 1:
            message = f"Hash uses {batches} batches; consider raising work_mem"
            findings.append(Finding("P004", "medium", label, message))

    # P005
    if node.node_type == "Nested Loop" and len(node.children) >= 2:
        inner = node.children[1]
        loops = _int(inner.fields, "Actual Loops")
        if loops is not None and loops > 1000:
            message = f"Nested Loop runs its inner side {loops} times"
            findings.append(Finding("P005", "medium", label, message))

    # P006
    temp_blocks = fields.get("Temp Written Blocks")
    if temp_blocks is not None:
        try:
            blocks = int(temp_blocks)
        except (TypeError, ValueError):
            blocks = 0
        if blocks > 0:
            message = f"{label} wrote {blocks} temp blocks"
            findings.append(Finding("P006", "low", label, message))

    return findings


def analyze(root: PlanRoot, *, top: int = 5) -> Report:
    """Compute exclusive timings, hotspots, and findings for a plan."""
    # Iterative postorder traversal
    stack1: list[PlanNode] = [root.plan]
    stack2: list[PlanNode] = []
    while stack1:
        node = stack1.pop()
        stack2.append(node)
        for child in node.children:
            stack1.append(child)

    postorder: list[PlanNode] = []
    while stack2:
        postorder.append(stack2.pop())

    total_by_id: dict[int, float] = {}
    exclusive_by_id: dict[int, float] = {}
    node_order: dict[int, int] = {}

    for idx, node in enumerate(postorder):
        node_order[id(node)] = idx
        fields = node.fields
        total_ms: float | None = None
        if "Actual Total Time" in fields and "Actual Loops" in fields:
            actual_time = _num(fields, "Actual Total Time")
            loops = _num(fields, "Actual Loops")
            if actual_time is not None and loops is not None:
                total_ms = actual_time * loops

        child_sum = 0.0
        for child in node.children:
            child_sum += total_by_id.get(id(child), 0.0)

        if total_ms is not None:
            exclusive = total_ms - child_sum
            if exclusive < 0:
                exclusive = 0.0
            exclusive = round(exclusive, 3)
            exclusive_by_id[id(node)] = exclusive
            total_by_id[id(node)] = total_ms

    analyzed = bool(exclusive_by_id)

    # Hotspots
    hotspot_candidates = [
        (exclusive_by_id[id(node)], node_order[id(node)], node)
        for node in postorder
        if id(node) in exclusive_by_id
    ]
    hotspot_candidates.sort(key=lambda x: (-x[0], x[1]))
    hotspots = tuple(
        Hotspot(node=_label(node), exclusive_ms=exclusive)
        for exclusive, _, node in hotspot_candidates[:top]
    )

    # Findings
    finding_tuples: list[tuple[int, str, Finding]] = []
    for node in postorder:
        order = node_order[id(node)]
        for finding in _node_findings(node):
            finding_tuples.append((order, finding.code, finding))
    finding_tuples.sort(key=lambda x: (x[0], x[1]))
    findings = tuple(f for _, _, f in finding_tuples)

    return Report(
        analyzed=analyzed,
        execution_ms=root.execution_ms,
        hotspots=hotspots,
        findings=findings,
    )


def render(report: Report) -> str:
    """Render a report as human-readable text."""
    lines: list[str] = []
    if report.execution_ms is not None:
        lines.append(f"Execution {report.execution_ms:.1f} ms")
        lines.append("")
    lines.append("Hotspots:")
    for spot in report.hotspots:
        lines.append(f"{spot.exclusive_ms:.1f} ms  {spot.node}")
    lines.append("")
    if report.findings:
        lines.append("Findings:")
        for f in report.findings:
            lines.append(f"{f.severity} {f.code} {f.message}")
    else:
        lines.append("Findings: none")
    return "\n".join(lines)
