"""Blueprint semantic content orchestrator (#554)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.blueprint.components import emit_components
from uasset_read.semantic.blueprint.flows import attach_flows
from uasset_read.semantic.blueprint.nodes import emit_graphs
from uasset_read.semantic.blueprint.reporting import BlueprintReporting
from uasset_read.semantic.blueprint.types import TypeTable
from uasset_read.semantic.blueprint.variables import emit_variables, emit_declaration

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def build_blueprint_content(package_ir: "PackageIR", export_ir: "ExportIR", coverage_model) -> dict:
    """Build the Blueprint domain content dict (BP-4 top-level shape)."""
    reporting = BlueprintReporting()
    table = TypeTable()

    # Content is built ONCE with evidence included (BP-3: parse once, mode
    # only affects evidence rendering). project_semantic strips `evidence`
    # keys recursively for standard; diagnostics occurrences live under
    # `evidence` too, so both modes derive from this single build.
    graphs = _collect_graphs(package_ir)
    if not graphs:
        reporting.coverage("graphs", "unavailable", reason="no_graph_exports")
        reporting.diagnostic("BP_GRAPH_MISSING", "asset", "warning", "semantic_loss")

    graphs_json, index = emit_graphs(graphs, table, reporting)
    attach_flows(graphs_json, index, reporting)

    # Graph completeness metrics
    _emit_graph_completeness(graphs, graphs_json, index, reporting)

    variables_json = emit_variables(getattr(package_ir, "variables", None) or [], table, reporting)
    blueprint = getattr(package_ir, "blueprint", None)
    components_json = emit_components(getattr(blueprint, "components", None) or [], table, reporting)

    declaration = emit_declaration(
        variable_names=[v["name"] for v in variables_json],
        component_ids=[c["id"] for c in components_json],
        functions=_function_index(blueprint, graphs_json),
        parent_class=getattr(blueprint, "parent_class", None) or "",
        interfaces=[
            i.get("name", "")
            for i in getattr(blueprint, "interfaces", None) or []
            if isinstance(i, dict) and i.get("name")
        ],
    )
    declaration.update(_asset_identity(package_ir, export_ir, blueprint))

    content: dict = {
        "references": [],  # blueprint format omits the raw import/export table
        "graphs": graphs_json,
    }
    if table.entries:
        content["types"] = table.entries
    if variables_json:
        content["variables"] = variables_json
    if components_json:
        content["components"] = components_json
    if declaration:
        content["declaration"] = declaration

    coverage_entries = reporting.coverage_entries()
    if coverage_entries:
        content["coverage"] = coverage_entries
    diagnostics = reporting.diagnostics_entries("debug")
    if diagnostics:
        content["diagnostics"] = diagnostics
    return content


def _asset_identity(package_ir, export_ir, blueprint) -> dict:
    """Blueprint-specific asset identity under declaration.asset."""
    identity: dict = {"kind": "blueprint"}
    parent = getattr(blueprint, "parent_class", None) or ""
    if parent:
        identity["parent_class"] = parent
    header = package_ir.header
    if getattr(header, "saved_by_engine_version", ""):
        identity["saved_by_engine"] = header.saved_by_engine_version
    return {"asset": identity}


def _collect_graphs(package_ir) -> list:
    """All GraphIR objects across exports, deduplicated by graph_guid, in
    deterministic export order."""
    seen: set[str] = set()
    graphs = []
    for export in package_ir.exports:
        for graph in getattr(export, "graphs", None) or []:
            guid = getattr(graph, "graph_guid", "") or f"{len(graphs)}:{getattr(graph, 'graph_name', '')}"
            if guid in seen:
                continue
            seen.add(guid)
            graphs.append(graph)
    return graphs


def _emit_graph_completeness(graphs, graphs_json, index, reporting) -> None:
    """Emit graph completeness metrics (nodes, pins, edges)."""
    # One recursive walk supplies totals for all three metrics; each is
    # compared against what was actually emitted (graphs_json / index).
    total_nodes, total_pins, total_edges = _count_graph_recursive(graphs)
    emitted_nodes = sum(len(g["nodes"]) for g in graphs_json)
    omitted_nodes = total_nodes - emitted_nodes

    emitted_pins = len(index)
    omitted_pins = total_pins - emitted_pins

    emitted_edges = _count_emitted_edges(graphs_json)
    omitted_edges = total_edges - emitted_edges

    # Determine status: "ok" if nothing omitted, "partial" if significant omissions
    node_status = "ok" if omitted_nodes == 0 else "partial"
    pin_status = "ok" if omitted_pins == 0 else "partial"
    edge_status = "ok" if omitted_edges == 0 else "partial"

    reporting.coverage(
        "graph_nodes",
        node_status,
        reason=f"{emitted_nodes}/{total_nodes} nodes emitted",
        declared=total_nodes,
        emitted=emitted_nodes,
        omitted=omitted_nodes,
    )
    reporting.coverage(
        "graph_pins",
        pin_status,
        reason=f"{emitted_pins}/{total_pins} pins emitted",
        declared=total_pins,
        emitted=emitted_pins,
        omitted=omitted_pins,
    )
    reporting.coverage(
        "graph_edges",
        edge_status,
        reason=f"{emitted_edges}/{total_edges} edges emitted",
        declared=total_edges,
        emitted=emitted_edges,
        omitted=omitted_edges,
    )


def _count_graph_recursive(graphs) -> tuple[int, int, int]:
    """Count (nodes, pins, edges) across all graphs, subgraphs included.

    Each linked_to entry on a pin counts as one edge.
    """
    nodes = pins = edges = 0
    for graph in graphs:
        for node in getattr(graph, "nodes", None) or []:
            nodes += 1
            for pin in getattr(node, "pins", None) or []:
                pins += 1
                edges += len(getattr(pin, "linked_to", None) or [])
        sub_nodes, sub_pins, sub_edges = _count_graph_recursive(getattr(graph, "subgraphs", None) or [])
        nodes += sub_nodes
        pins += sub_pins
        edges += sub_edges
    return nodes, pins, edges


def _count_emitted_edges(graphs_json) -> int:
    """Count edges actually emitted in control_flow and data_flow."""
    count = 0
    for graph in graphs_json:
        control = graph.get("control_flow", {})
        count += len(control.get("edges", []))
        data = graph.get("data_flow", {})
        count += len(data.get("edges", []))
    return count


def _function_index(blueprint, graphs_json) -> list[dict]:
    """Function declarations joined to implementation graphs by name."""
    graph_by_name = {g["name"]: g["id"] for g in graphs_json}
    functions = []
    for fn in getattr(blueprint, "functions", None) or []:
        name = getattr(fn, "name", "") or ""
        if not name:
            continue
        functions.append({"name": name, "graph": graph_by_name.get(name)})
    return functions
