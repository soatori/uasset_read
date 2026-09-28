"""Blueprint graph decode-pass support (issue #621 Phase 4.5).

The v2 handler layer never touches the archive, but editor-saved graph pins
are not exports — they are serialized inside each node export's serial region
after the tagged property stream. The fixture-proven binary readers in
``serializers/graph*.py`` are v1 modules this plan reuses unchanged (first v2
consumer, reader-layer reuse like serializers/object_resources.py — not v1
extractor bridging per D2). This module is the v2 decode-pass seam: it runs
those readers once per package at depth="decode" and converts the result into
JSON-safe plain dicts that travel through the ``extras`` channel
(``package_data[2]``) to the handlers.

UE source: UEdGraph::Serialize / UEdGraphNode::Serialize /
UEdGraphPin::Serialize in Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraph*.h.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from uasset_read.models.byte_ranges import ByteRegion, project_region
from uasset_read.serializers.node_data_project import project_node_data as _project_node_data

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

logger = logging.getLogger(__name__)

# Hard caps on converted output. Values chosen so the largest tracked package
# (ALS_AnimBP: 275 graphs, ~2,700 node exports) passes without cap engagement
# while runaway editor graphs stay bounded (canonical design: bounded by default).
MAX_GRAPHS_PER_PACKAGE = 512
MAX_NODES_PER_GRAPH_OUTPUT = 512
MAX_PINS_PER_NODE_OUTPUT = 64


def _validate_graph_export_offset(export, archive_size: int) -> bool:
    """Validate whether a graph export's serialization offset is within valid range.

    When serial_offset is 0 and serial_size > 0, the offset is abnormal (non-Default__ export).
    When serial_offset + serial_size exceeds archive boundary, data is truncated.
    """
    serial_offset = getattr(export, "serial_offset", 0)
    serial_size = getattr(export, "serial_size", 0)

    if serial_size == 0:
        return True  # empty export, skip check

    # Check for negative values
    if serial_offset < 0 or serial_size < 0:
        logger.warning(
            "Graph export '%s' offset abnormal: offset=%d, size=%d",
            export.object_name,
            serial_offset,
            serial_size,
        )
        return False

    # Offset should not be 0 (unless it is a special Default__ export)
    if serial_offset == 0 and not str(getattr(export, "object_name", "")).startswith("Default__"):
        logger.warning(
            "Graph export '%s' serial_offset=0 and serial_size=%d, offset abnormal",
            export.object_name,
            serial_size,
        )
        return False

    # Check if exceeding archive boundary
    if archive_size > 0 and serial_offset + serial_size > archive_size:
        logger.warning(
            "Graph export '%s' offset out of bounds: offset=%d + size=%d > archive_size=%d",
            export.object_name,
            serial_offset,
            serial_size,
            archive_size,
        )
        return False

    return True


def _is_graph_class(class_name: str | None) -> bool:
    """Narrower than v1's EDGRAPH_CLASS_NAMES — only real UEdGraph containers."""
    if not class_name:
        return False
    return class_name.endswith("Graph")


def read_blueprint_graphs(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list[Any],
    export_map: list[ObjectExport],
) -> list[dict[str, Any]]:
    """Parse all graph exports in the package and return plain graph dicts.

    Runs the shared binary readers (serializers/graph.read_ue_graph per graph
    export) and converts the resulting UEdGraph trees. Never raises on a
    single bad graph: failures produce a dict-level ``parse_errors`` count and
    the caller's diagnostics cover it. The archive must be open on the full
    package (decode pass restores the full read range before calling).
    """
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import resolve_class_name

    archive_size = 0
    if archive is not None:
        try:
            archive_size = archive.total_size()
        except (OSError, AttributeError):
            archive_size = 0

    graphs: list[dict[str, Any]] = []
    processed = 0
    for export_idx, export in enumerate(export_map):
        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if not class_name or not _is_graph_class(class_name):
            continue
        if processed >= MAX_GRAPHS_PER_PACKAGE:
            break
        processed += 1
        try:
            if not _validate_graph_export_offset(export, archive_size):
                graphs.append(_error_graph(export_idx, class_name, "offset validation failed"))
                continue
            graph = read_ue_graph(
                archive,
                name_map,
                summary,
                export_map,
                import_map,
                export,
                export_idx + 1,  # 1-based index
            )
            graphs.append(_graph_to_dict(graph, export_idx, class_name))
        except Exception as exc:  # one bad graph must not kill the decode pass
            graphs.append(_error_graph(export_idx, class_name, f"{type(exc).__name__}: {exc}"))
    resolve_pin_links(graphs)
    return graphs


def _error_graph(export_idx: int, class_name: str, reason: str) -> dict[str, Any]:
    return {
        "id": f"export:{export_idx}",
        "name": "",
        "graph_class": class_name or "",
        "kind": "unknown",
        "nodes": [],
        "node_count": 0,
        "pin_count": 0,
        "edge_count": 0,
        "truncated": {"nodes": False, "pins": False},
        "parse_errors": [reason],
    }


def _convert_nodes(graph: Any, nodes: list[dict[str, Any]], pin_count: int, node_limit: int) -> tuple[int, bool, bool]:
    """Convert nodes from a UEdGraph into dicts, appending to *nodes*.

    Returns (pin_count, node_truncated, pin_truncated).
    """
    node_truncated = False
    pin_truncated = False
    for node in graph.nodes:
        if len(nodes) >= node_limit:
            node_truncated = True
            break
        pins: list[dict[str, Any]] = []
        for pin in node.pins:
            if len(pins) >= MAX_PINS_PER_NODE_OUTPUT:
                pin_truncated = True
                break
            pin_type = pin.pin_type
            pin_dict: dict[str, Any] = {
                "id": str(pin.pin_id),
                "name": str(pin.pin_name),
                # EEdGraphPinDirection: EGPD_Input = 0, EGPD_Output = 1
                "direction": {0: "input", 1: "output"}.get(pin.direction, "unknown"),
                "category": str(pin_type.pin_category) if pin_type else "",
                "linked": [],
            }
            # Optional Task-6 retention: omit null/empty defaults so large
            # AnimBlueprint pages stay within project_document byte budgets.
            subcategory = str(getattr(pin, "sub_category", "") or "")
            if subcategory:
                pin_dict["subcategory"] = subcategory
            if getattr(pin, "default_value", None) is not None:
                pin_dict["default_value"] = pin.default_value
            if getattr(pin, "default_object_ref", None) is not None:
                pin_dict["default_object_ref"] = pin.default_object_ref
            if getattr(pin, "default_text", None) is not None:
                pin_dict["default_text"] = pin.default_text
            sub_pin_ids = list(getattr(pin, "sub_pin_ids", None) or [])
            if sub_pin_ids:
                pin_dict["sub_pin_ids"] = sub_pin_ids
            if getattr(pin, "parent_pin_id", None) is not None:
                pin_dict["parent_pin_id"] = pin.parent_pin_id
            if getattr(pin, "reference_pass_through_pin_id", None) is not None:
                pin_dict["reference_pass_through_pin_id"] = pin.reference_pass_through_pin_id
            if getattr(pin, "is_const", False):
                pin_dict["is_const"] = True
            pins.append(pin_dict)
        pin_count += len(pins)
        short_id = f"export:{node._export_index - 1}" if getattr(node, "_export_index", 0) else ""
        class_name = str(node.class_name or "")
        # Display name: export object names were removed from the reader path
        # (Wave A); use class_name + short id instead of the graph name.
        display_name = f"{class_name}:{short_id}" if class_name and short_id else (class_name or short_id)
        node_dict: dict[str, Any] = {
            "id": short_id,
            "type": class_name,
            "name": display_name,
            "position": {
                "x": int(node.node_pos_x or 0),
                "y": int(node.node_pos_y or 0),
            },
            "pins": pins,
        }
        anim_data = _project_node_data(getattr(node, "node_data", None))
        if anim_data is not None:
            node_dict["node_data"] = anim_data
        nodes.append(node_dict)
    return pin_count, node_truncated, pin_truncated


def _collect_pin_links_recursive(graph: Any) -> list[dict[str, Any]]:
    """Collect pin links from a UEdGraph and all its subgraphs."""
    links = _collect_pin_links(graph)
    for sub in graph.subgraphs:
        links.extend(_collect_pin_links_recursive(sub))
    return links


def _graph_to_dict(graph: Any, export_idx: int, class_name: str) -> dict[str, Any]:
    """Convert one UEdGraph tree into a JSON-safe dict (bounded).

    Recursively flattens subgraph nodes into the parent's ``nodes`` list,
    since UE subgraphs are a visual-organization concept and the output
    contract uses a flat node array per graph.
    """
    nodes: list[dict[str, Any]] = []
    pin_count = 0
    node_truncated = False
    pin_truncated = False

    # Top-level nodes
    pin_count, node_truncated, pin_truncated = _convert_nodes(graph, nodes, pin_count, MAX_NODES_PER_GRAPH_OUTPUT)
    # Subgraph nodes (flattened into the same list)
    for sub in graph.subgraphs:
        if node_truncated:
            break
        sub_pin_count, sub_node_trunc, sub_pin_trunc = _convert_nodes(sub, nodes, pin_count, MAX_NODES_PER_GRAPH_OUTPUT)
        pin_count = sub_pin_count
        if sub_node_trunc:
            node_truncated = True
        if sub_pin_trunc:
            pin_truncated = True

    # Node-level recovery reasons (empty for a clean graph). Whole-graph
    # failures use _error_graph instead and never reach this converter.
    # Subgraph node failures surface here too because subgraph nodes are
    # flattened into this projection.
    parse_errors: list[str] = list(getattr(graph, "parse_errors", []) or [])
    for sub in graph.subgraphs:
        parse_errors.extend(str(e) for e in (getattr(sub, "parse_errors", []) or []))

    return {
        "id": f"export:{export_idx}",
        "name": str(graph.graph_name or ""),
        "graph_class": class_name,
        "kind": "unknown",  # finalized by the handler from name / FunctionGraphs
        "nodes": nodes,
        "node_count": len(nodes),
        "pin_count": pin_count,
        "edge_count": 0,  # set by resolve_pin_links
        "truncated": {"nodes": node_truncated, "pins": pin_truncated},
        "parse_errors": parse_errors,
        "_pin_links": _collect_pin_links_recursive(graph),
        "_pin_ranges": _pin_ranges_of(graph),
    }


def _pin_ranges_of(graph: Any) -> dict[tuple[str, str], ByteRegion]:
    """(node id, pin id) -> serialization span, for target_pin_range lookups."""
    out: dict[tuple[str, str], ByteRegion] = {}
    for container in (graph, *graph.subgraphs):
        for node in container.nodes:
            node_id = f"export:{node._export_index - 1}" if getattr(node, "_export_index", 0) else ""
            for pin in node.pins:
                if node_id and pin.pin_id and pin.serial_range is not None:
                    out[(node_id, str(pin.pin_id))] = pin.serial_range
    return out


def _owner_object_id(raw_owner: Any) -> str | None:
    """Serialized FPackageIndex -> stable object id (positive export, negative import)."""
    if isinstance(raw_owner, int) and raw_owner > 0:
        return f"export:{raw_owner - 1}"
    if isinstance(raw_owner, int) and raw_owner < 0:
        return f"import:{-raw_owner - 1}"
    return None


def _connection_type(category: Any) -> str:
    """Source-pin category -> connection_type enum (source side only)."""
    text = str(category or "")
    if text == "exec":
        return "exec"
    if text in {"delegate", "mcdelegate"}:
        return "delegate"
    if text:
        return "data"
    return "unknown"


def _ref_region(bounds: Any) -> ByteRegion | None:
    if isinstance(bounds, tuple) and len(bounds) == 2 and all(isinstance(v, int) for v in bounds):
        start, end = bounds
        if end >= start:
            return ByteRegion(start, end - start, "decoded", feature="blueprint.pin_reference")
    return None


def _collect_pin_links(graph: Any) -> list[dict[str, Any]]:
    """Collect (source pin, target pin-ref) link records from one UEdGraph tree.

    ``UEdGraphPin.linked_to_raw`` entries are
    ``{"owning_node": <raw FPackageIndex int>, "pin_guid": <target 32-hex>}``
    — the *target's* owning node and GUID (verified on the tracked fixtures);
    the source is the pin owning the list. Each record carries the owning
    pin's own id (``from_pin``) plus the target identity fields, the source
    pin category, and the raw byte ranges needed for GraphLinkDebugEvidence.
    """
    links: list[dict[str, Any]] = []
    for node in graph.nodes:
        for pin in node.pins:
            category = str(pin.pin_type.pin_category) if pin.pin_type else ""
            for entry in pin.linked_to_raw:
                links.append(
                    {
                        "from_node": getattr(node, "_export_index", 0),  # 1-based
                        "from_pin": str(pin.pin_id),
                        "to_pin": str(entry["pin_guid"]) if entry.get("pin_guid") else None,
                        "to_owning_node": entry.get("owning_node"),
                        "null": bool(entry.get("null")),
                        "source_category": category,
                        "source_pin_range": pin.serial_range,
                        "ref_range": entry.get("ref_range"),
                    }
                )
    return links


def resolve_pin_links(graphs: list[dict[str, Any]]) -> None:
    """Resolve every graph's GUID-keyed links and retain one record per slot.

    Emits ``graph["links"]``: exactly one raw record per serialized
    ``LinkedTo`` slot — resolved, unresolved, ambiguous, import-owned, or
    null. Target lookup and the counters keep their historical semantics
    (owner key first; GUID-only fallback only when the owner is unavailable
    and exactly one candidate carries the GUID); pin ``linked`` adjacency,
    ``edge_count``, ``unresolved_links`` and ``ambiguous_links`` stay derived
    views of the same walk. Raw records carry bare export ids; the typed
    decoder adds the owner prefix required by the schema GraphId/NodeId
    patterns. Consumes and deletes ``_pin_links`` and ``_pin_ranges``.
    """
    # The emitter inlines subgraph nodes into their owning graph's ``nodes``
    # list (see ``_graph_to_dict``), so an emitted graph dict carries no
    # ``subgraphs`` key. The same physical node export can still appear in
    # several emitted graphs — dedupe candidates by (node id, pin id).
    all_nodes = [n for g in graphs for n in g.get("nodes", [])]
    owner_pins: set[tuple[str, str]] = set()
    by_guid: dict[str, list[tuple[str, str]]] = {}
    for node in all_nodes:
        for pin in node.get("pins", []):
            if pin["id"]:
                entry = (node["id"], pin["id"])
                owner_pins.add(entry)
                by_guid.setdefault(pin["id"], []).append(entry)
    # Flatten repeated (node, pin) entries from multi-graph appearances.
    by_guid = {k: list(dict.fromkeys(v)) for k, v in by_guid.items()}

    pin_ranges: dict[tuple[str, str], ByteRegion] = {}
    for graph in graphs:
        pin_ranges.update(graph.pop("_pin_ranges", None) or {})

    for graph in graphs:
        graph["unresolved_links"] = 0
        graph["ambiguous_links"] = 0
        edge_count = 0
        records: list[dict[str, Any]] = []
        for rec in graph.pop("_pin_links", []):
            guid = rec.get("to_pin")
            raw_owner = rec.get("to_owning_node")
            source_node_export = f"export:{rec['from_node'] - 1}"
            source_pin_guid = str(rec.get("from_pin") or "")
            target: tuple[str, str] | None = None
            target_node_export: str | None = None

            if rec.get("null"):
                status, reason = "unresolved", "null_link_reference"
            elif isinstance(raw_owner, int) and raw_owner < 0:
                # Negative FPackageIndex = import: outside this package's
                # export table — never resolve it to a local GUID match.
                status, reason = "unresolved", "target_owner_is_import"
            elif isinstance(raw_owner, int) and raw_owner > 0:
                owner = f"export:{raw_owner - 1}"
                target_node_export = owner
                if (owner, guid) in owner_pins:
                    target = (owner, guid)
                    status, reason = "resolved", "owner_and_guid_match"
                else:
                    status, reason = "unresolved", "target_pin_not_found"
            else:
                candidates = by_guid.get(guid, [])
                if len(candidates) == 1:
                    target = candidates[0]
                    target_node_export = target[0]
                    status, reason = "resolved", "unique_guid_without_owner"
                elif len(candidates) > 1:
                    status, reason = "ambiguous", "multiple_guid_candidates_without_owner"
                else:
                    status, reason = "unresolved", "no_candidate_for_guid"

            records.append(
                {
                    "_source_node_export": source_node_export,
                    "source_pin_guid": source_pin_guid,
                    "target_owner_id": _owner_object_id(raw_owner),
                    "_target_node_export": target_node_export,
                    "target_pin_guid": str(guid) if guid else None,
                    "connection_type": _connection_type(rec.get("source_category")),
                    "status": status,
                    "reason": reason,
                    "debug_evidence": {
                        "raw_source_owner_package_index": rec["from_node"],
                        "raw_target_owner_package_index": raw_owner if isinstance(raw_owner, int) else None,
                        "raw_source_pin_guid": source_pin_guid,
                        "raw_target_pin_guid": str(guid) if guid else None,
                        "source_pin_range": project_region(rec.get("source_pin_range")),
                        "target_reference_range": project_region(_ref_region(rec.get("ref_range"))),
                        "target_pin_range": (
                            project_region(pin_ranges.get(target)) if target is not None else None
                        ),
                    },
                }
            )

            if status == "resolved":
                edge_count += 1
            else:
                graph["unresolved_links"] += 1
                if status == "ambiguous":
                    graph["ambiguous_links"] += 1
            if target is None:
                continue
            for node in graph["nodes"]:
                if node["id"] != source_node_export:
                    continue
                for pin in node["pins"]:
                    if pin["id"] == rec["from_pin"]:
                        pin["linked"].append({"to_node": target[0], "to_pin": target[1]})
        graph["links"] = records
        graph["edge_count"] = edge_count


def summarize_exec_edges(graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize exec-pin (category=exec) edges per graph.

    Consumes the five-key pin projection (category + linked already resolved
    by ``resolve_pin_links``). Each undirected pin connection is emitted once
    (bidirectional ``linked`` entries are reverse pairs). Endpoints use pin
    ids on both sides so consumers can join; when both orientations exist the
    edge prefers output→input. Distinct from ``graph["edge_count"]``, which
    counts every resolved link record. Graphs with no exec edges are omitted.

    ``to_node`` comes from the owner-aware ``link["to_node"]`` written by
    ``resolve_pin_links`` — never from a package-wide pin-GUID map (duplicate
    pin GUIDs across nodes would make the last registration win). Undirected
    uniqueness keys on frozensets of ``(node_id, pin_id)`` endpoint pairs so
    distinct node/pin pairs sharing a pin GUID stay distinct edges.

    Orientation flip only prefers an output endpoint when the current pin is
    not already output. It does not re-validate that the peer pin's category
    is also ``exec``: the walk already required *this* pin to be exec, and
    filtering on the peer would drop legitimate edges recorded on only one
    side of the link table.
    """
    out: list[dict[str, Any]] = []
    for graph in graphs:
        # Direction lookup only — never override the owner-aware to_node.
        # Key is (node_id, pin_id) so duplicate pin GUIDs across nodes stay distinct.
        pin_direction: dict[tuple[str, str], str] = {}
        for node in graph.get("nodes") or []:
            for pin in node.get("pins") or []:
                pid = pin.get("id")
                nid = node.get("id")
                if pid and nid:
                    pin_direction[(nid, pid)] = pin.get("direction") or ""

        seen: set[frozenset[tuple[str, str]]] = set()
        edges: list[dict[str, Any]] = []
        for node in graph.get("nodes") or []:
            for pin in node.get("pins") or []:
                if (pin.get("category") or "") != "exec":
                    continue
                for link in pin.get("linked") or []:
                    from_id = pin.get("id")
                    to_id = link.get("to_pin")
                    from_node = node.get("id")
                    to_node = link.get("to_node")
                    if not from_id or not to_id or from_id == to_id:
                        continue
                    if not from_node or not to_node:
                        continue
                    pair = frozenset({(from_node, from_id), (to_node, to_id)})
                    if pair in seen:
                        continue
                    seen.add(pair)
                    if pin.get("direction") != "output":
                        other_dir = pin_direction.get((to_node, to_id), "")
                        if other_dir == "output":
                            from_id, to_id = to_id, from_id
                            from_node, to_node = to_node, from_node
                    edges.append(
                        {
                            "from_node": from_node,
                            "from_pin": from_id,
                            "to_node": to_node,
                            "to_pin": to_id,
                        }
                    )
        if edges:
            out.append({"graph": graph.get("name"), "edges": edges})
    return out
