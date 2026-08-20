"""Inter-function call graph construction for Blueprint functions.

Analyzes function dependencies and execution flows across Blueprint functions
by scanning EX_FinalFunction / EX_VirtualFunction / EX_LocalFinalFunction /
EX_LocalVirtualFunction expressions.

Usage:
    from uasset_read.kismet.call_graph import build_call_graph, CallGraph

    graph = build_call_graph(functions)
    for caller, callees in graph.edges.items():
        print(f"{caller} calls {callees}")
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker


@dataclass
class CallEdge:
    """A directed call edge from caller to callee."""

    caller: str
    """Calling function name."""

    callee: str
    """Called function name."""

    call_type: str
    """Call type: 'final', 'virtual', 'local_final', 'local_virtual'."""

    expression_index: int = -1
    """Expression index in the calling function (for diagnostics)."""


@dataclass
class CallGraph:
    """Inter-function call graph."""

    edges: dict[str, list[CallEdge]] = field(default_factory=dict)
    """caller_name -> list of CallEdge"""

    @property
    def all_callers(self) -> set[str]:
        """Set of function names that make calls."""
        return set(self.edges.keys())

    @property
    def all_callees(self) -> set[str]:
        """Set of function names that are called."""
        return {edge.callee for edges in self.edges.values() for edge in edges}

    def has_cycle(self) -> bool:
        """Detect if the call graph contains a cycle (mutual recursion)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {}

        all_nodes = self.all_callers | self.all_callees
        for node in all_nodes:
            color[node] = WHITE

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for edge in self.edges.get(node, []):
                callee = edge.callee
                if color.get(callee) == GRAY:
                    return True
                if color.get(callee) == WHITE:
                    if dfs(callee):
                        return True
            color[node] = BLACK
            return False

        for node in all_nodes:
            if color.get(node) == WHITE:
                if dfs(node):
                    return True
        return False

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        result = {}
        for caller, edges in self.edges.items():
            result[caller] = [
                {
                    "callee": e.callee,
                    "call_type": e.call_type,
                    "expression_index": e.expression_index,
                }
                for e in edges
            ]
        return result


def _extract_called_functions_from_expression(
    expr,
    linker: Optional["PackageLinker"] = None,
) -> list[tuple[str, str]]:
    """Extract function names from a single expression.

    Returns list of (callee_name, call_type).
    """
    from uasset_read.kismet.expressions.functions import (
        EX_FinalFunction, EX_VirtualFunction,
        EX_LocalFinalFunction, EX_LocalVirtualFunction,
    )

    results: list[tuple[str, str]] = []

    if isinstance(expr, (EX_FinalFunction, EX_LocalFinalFunction)):
        # EX_FinalFunction uses StackNode (int) - resolve via linker
        stack_node = getattr(expr, "StackNode", 0)
        if isinstance(stack_node, int) and stack_node != 0:
            if linker is not None:
                from uasset_read.kismet.function_resolver import FunctionRefResolver
                resolver = FunctionRefResolver(linker)
                resolved = resolver.resolve(stack_node)
                if resolved is not None:
                    class_name, func_name = resolved
                    call_type = "final" if isinstance(expr, EX_FinalFunction) else "local_final"
                    results.append((func_name, call_type))
            else:
                # Fallback: use StackNode as identifier
                call_type = "final" if isinstance(expr, EX_FinalFunction) else "local_final"
                results.append((f"Function_{stack_node}", call_type))

    elif isinstance(expr, (EX_VirtualFunction, EX_LocalVirtualFunction)):
        # EX_VirtualFunction uses VirtualFunctionName (string)
        func_name = getattr(expr, "VirtualFunctionName", "")
        if func_name and isinstance(func_name, str):
            call_type = "virtual" if isinstance(expr, EX_VirtualFunction) else "local_virtual"
            results.append((func_name, call_type))

    return results


def _walk_expressions(expr, callback) -> None:
    """Walk expression tree, calling callback for each expression."""
    if expr is None:
        return

    callback(expr)

    # Recurse into child expressions
    for attr_name in ("SubExpressions", "Args", "Parameters", "TrueExpr", "FalseExpr",
                      "Then", "Else", "Body", "SourceExpression"):
        child = getattr(expr, attr_name, None)
        if child is None:
            continue
        if isinstance(child, list):
            for item in child:
                _walk_expressions(item, callback)
        else:
            _walk_expressions(child, callback)


def build_call_graph(
    functions: list,
    linker: Optional["PackageLinker"] = None,
) -> CallGraph:
    """Build inter-function call graph from a list of BlueprintFunction objects.

    Args:
        functions: List of BlueprintFunction objects with bytecode expressions
        linker: Optional PackageLinker for resolving StackNode references

    Returns:
        CallGraph with caller->callee edges
    """
    graph = CallGraph()

    for func in functions:
        func_name = getattr(func, "name", None)
        if not func_name:
            continue

        # Get expressions from the function
        expressions = getattr(func, "expressions", None) or []
        if not expressions:
            # Try to get from body_ir
            body_ir = getattr(func, "body_ir", None)
            if body_ir:
                expressions = getattr(body_ir, "expressions", []) or []

        # Scan expressions for function calls
        edges: list[CallEdge] = []

        def _scan_expr(expr) -> None:
            calls = _extract_called_functions_from_expression(expr, linker)
            for callee_name, call_type in calls:
                expr_idx = getattr(expr, "_expr_index", -1)
                edges.append(CallEdge(
                    caller=func_name,
                    callee=callee_name,
                    call_type=call_type,
                    expression_index=expr_idx,
                ))

        for expr in expressions:
            _walk_expressions(expr, _scan_expr)

        if edges:
            graph.edges[func_name] = edges

    return graph
