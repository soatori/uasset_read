"""Animation Blueprint semantic content orchestrator.

Builds the anim_blueprint_semantic domain content from PackageIR and ExportIR.
Extends the Blueprint semantic infrastructure with animation-specific data:
- Baked state machines with states and transitions
- Animation notifies
- Sync groups
- Pose flows for animation pose connections
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.anim_blueprint.nodes import (
    anim_graph_kind,
    emit_anim_node,
)
from uasset_read.semantic.anim_blueprint.state_machines import emit_state_machines
from uasset_read.semantic.anim_blueprint.flows import attach_flows
from uasset_read.semantic.blueprint.ids import ascii_slug
from uasset_read.semantic.blueprint.reporting import BlueprintReporting
from uasset_read.semantic.blueprint.types import TypeTable
from uasset_read.semantic.blueprint.variables import emit_variables, emit_declaration
from uasset_read.semantic.blueprint.components import emit_components

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def _find_anim_blueprint_ir(package_ir, primary_export):
    """Find AnimBlueprintIR from primary export or generated class.

    Priority:
    1. Primary export has anim_blueprint data -> use it
    2. Search exports in serialization order for generated class data
    3. None if not found
    """
    direct = getattr(primary_export, "anim_blueprint", None)
    if direct is not None:
        return direct
    return next(
        (export.anim_blueprint for export in package_ir.exports if getattr(export, "anim_blueprint", None) is not None),
        None,
    )


def _report_opaque_coverage(graphs_json: list[dict], reporting) -> None:
    """Report coverage for opaque (unrecognized) nodes."""
    total_nodes = 0
    opaque_nodes = 0
    for graph in graphs_json:
        for node in graph.get("nodes", []):
            total_nodes += 1
            if node.get("status") == "opaque":
                opaque_nodes += 1

    if opaque_nodes > 0:
        reporting.coverage(
            "nodes",
            "partial",
            reason="opaque_nodes",
            declared=total_nodes,
            emitted=total_nodes,
            omitted=0,
        )


def build_anim_blueprint_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
    evidence_list,
) -> dict:
    """Build the Animation Blueprint domain content dict.

    This is the main orchestrator that:
    1. Extracts graphs from UEdGraph data (reuses blueprint graph extraction)
    2. Extracts state machines from AnimBlueprintIR
    3. Extracts animation notifies
    4. Extracts sync groups
    5. Extracts variables and components (reuses from blueprint)
    6. Emits pose flows for animation pose connections
    """
    reporting = BlueprintReporting()
    table = TypeTable()

    # Get animation data from export
    anim_blueprint = _find_anim_blueprint_ir(package_ir, export_ir)

    # --- Graphs ---
    graphs = _collect_graphs(package_ir)
    if not graphs:
        reporting.coverage("graphs", "unavailable", reason="no_graph_exports")
        reporting.diagnostic("ABP_GRAPH_MISSING", "asset", "warning", "semantic_loss")

    # Content is always built with debug evidence; project_semantic strips
    # it for standard mode (same contract as the blueprint extractor).
    graphs_json, index = _emit_anim_graphs(graphs, table, reporting)
    attach_flows(graphs_json, index, reporting)

    # Report opaque node coverage
    _report_opaque_coverage(graphs_json, reporting)

    # --- State Machines ---
    state_machines = []
    if anim_blueprint is not None:
        baked_machines = getattr(anim_blueprint, "baked_state_machines", []) or []
        state_machines = emit_state_machines(baked_machines, reporting)
    else:
        reporting.coverage("state_machines", "unavailable", reason="no_anim_blueprint_data")

    # --- Animation Notifies ---
    anim_notifies = []
    if anim_blueprint is not None:
        notifies = getattr(anim_blueprint, "anim_notifies", []) or []
        anim_notifies = _emit_anim_notifies(notifies, reporting)
    else:
        reporting.coverage("anim_notifies", "unavailable", reason="no_anim_blueprint_data")

    # --- Sync Groups ---
    sync_groups = []
    if anim_blueprint is not None:
        sync_groups = getattr(anim_blueprint, "sync_group_names", []) or []

    # --- Variables and Components ---
    blueprint = getattr(package_ir, "blueprint", None)
    variables_json = emit_variables(getattr(package_ir, "variables", None) or [], table, reporting)
    components_json = emit_components(getattr(blueprint, "components", None) or [], table, reporting)

    # --- Declaration ---
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
    declaration.update(_asset_identity(package_ir, export_ir, anim_blueprint))

    # --- Build content ---
    content: dict = {
        "references": [],
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
    if state_machines:
        content["state_machines"] = state_machines
    if anim_notifies:
        content["anim_notifies"] = anim_notifies
    if sync_groups:
        content["sync_groups"] = sync_groups

    coverage_entries = reporting.coverage_entries()
    if coverage_entries:
        content["coverage"] = coverage_entries
    diagnostics = reporting.diagnostics_entries("debug")
    if diagnostics:
        content["diagnostics"] = diagnostics

    return content


def _asset_identity(package_ir, export_ir, anim_blueprint) -> dict:
    """Animation Blueprint-specific asset identity under declaration.asset."""
    identity: dict = {"kind": "anim_blueprint"}
    target_skeleton = getattr(anim_blueprint, "target_skeleton", None) if anim_blueprint else None
    if target_skeleton:
        identity["target_skeleton"] = target_skeleton
    header = package_ir.header
    if getattr(header, "saved_by_engine_version", ""):
        identity["saved_by_engine"] = header.saved_by_engine_version
    return {"asset": identity}


def _collect_graphs(package_ir) -> list:
    """All GraphIR objects across exports, deduplicated by graph_guid."""
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


def _emit_anim_graphs(graphs, table, reporting) -> tuple[list[dict], dict]:
    """Emit graphs with animation-specific node kinds."""
    graphs_json: list[dict] = []
    index: dict[str, dict] = {}
    graph_slug_counts: dict[str, int] = {}

    def emit(graph) -> None:
        name = getattr(graph, "graph_name", "") or "Graph"
        graph_class = getattr(graph, "graph_class", "") or ""
        slug = ascii_slug(name)
        seen = graph_slug_counts.get(slug, 0)
        graph_slug_counts[slug] = seen + 1
        if seen:
            slug = f"{slug}_{seen}"

        gid = f"animblueprint://graph/{slug}"
        nodes_json: list[dict] = []
        ordinal_counts: dict[tuple[str, str], int] = {}

        for node in getattr(graph, "nodes", None) or []:
            node_json, node_index = emit_anim_node(node, slug, ordinal_counts, table, reporting)
            if node_json is None:
                continue
            nodes_json.append(node_json)
            index.update(node_index)

        kind = anim_graph_kind(name, graph_class)
        if kind == "event_graph" and any(
            emit_anim_node(n, slug, {}, table, reporting)[0]
            and emit_anim_node(n, slug, {}, table, reporting)[0].get("kind") == "function_entry"
            for n in getattr(graph, "nodes", None) or []
        ):
            kind = "function"

        entry: dict = {
            "id": gid,
            "name": name,
            "kind": kind,
            "nodes": nodes_json,
            "evidence": {"graph_guid": getattr(graph, "graph_guid", "") or ""},
        }
        graphs_json.append(entry)

        for subgraph in getattr(graph, "subgraphs", None) or []:
            emit(subgraph)

    for graph in graphs:
        emit(graph)

    return graphs_json, index


def _emit_anim_notifies(notifies: list, reporting) -> list[dict]:
    """Emit animation notifies."""
    notifies_json: list[dict] = []

    for notify in notifies:
        notify_dict: dict = {
            "name": getattr(notify, "notify_name", "") or "",
        }

        trigger_offset = getattr(notify, "trigger_time_offset", 0.0)
        if trigger_offset != 0.0:
            notify_dict["trigger_time_offset"] = trigger_offset

        duration = getattr(notify, "duration", 0.0)
        if duration != 0.0:
            notify_dict["duration"] = duration

        notify_class = getattr(notify, "notify_class", None)
        if notify_class:
            notify_dict["notify_class"] = notify_class

        notify_state_class = getattr(notify, "notify_state_class", None)
        if notify_state_class:
            notify_dict["notify_state_class"] = notify_state_class

        track_index = getattr(notify, "track_index", 0)
        if track_index != 0:
            notify_dict["track_index"] = track_index

        evidence: dict = {}
        end_offset = getattr(notify, "end_trigger_time_offset", 0.0)
        if end_offset != 0.0:
            evidence["end_trigger_time_offset"] = end_offset
        weight_threshold = getattr(notify, "trigger_weight_threshold", 0.0)
        if weight_threshold != 0.0:
            evidence["trigger_weight_threshold"] = weight_threshold
        tick_type = getattr(notify, "montage_tick_type", None)
        if tick_type:
            evidence["montage_tick_type"] = tick_type
        trigger_chance = getattr(notify, "notify_trigger_chance", 1.0)
        if trigger_chance != 1.0:
            evidence["notify_trigger_chance"] = trigger_chance
        filter_type = getattr(notify, "notify_filter_type", None)
        if filter_type:
            evidence["notify_filter_type"] = filter_type
        filter_lod = getattr(notify, "notify_filter_lod", 0)
        if filter_lod != 0:
            evidence["notify_filter_lod"] = filter_lod
        converted = getattr(notify, "b_converted_from_branching_point", False)
        if converted:
            evidence["b_converted_from_branching_point"] = True
        linked_montage = getattr(notify, "linked_montage", None)
        if linked_montage:
            evidence["linked_montage"] = linked_montage
        linked_sequence = getattr(notify, "linked_sequence", None)
        if linked_sequence:
            evidence["linked_sequence"] = linked_sequence
        if evidence:
            notify_dict["evidence"] = evidence

        notifies_json.append(notify_dict)

    return notifies_json


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
