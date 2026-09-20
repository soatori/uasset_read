"""Owner-aware Blueprint graph IR bridge.

``read_blueprint_graphs`` remains the raw binary serializer boundary
(``list[dict]``). This module is the single dict→typed-IR conversion and
typed pin-link resolution used by correlation/projections.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from uasset_read.models.analysis import (
    BlueprintGraph,
    BlueprintNode,
    BlueprintPin,
    GraphId,
    K2NodeMetadata,
    LinkResolution,
    NodeId,
    PinLink,
    PinLinkRef,
    project_blueprint_graph,
    project_k2_metadata,
    project_opaque,
    project_pin_link,
)
from uasset_read.models.byte_ranges import ByteRegion, opaque_region
from uasset_read.models.diagnostics import Diagnostic

if TYPE_CHECKING:
    from uasset_read.models.document import PackageDocument
    from uasset_read.models.object_model import ObjectRecord
    from uasset_read.sources import ByteSource

__all__ = [
    "BlueprintGraphDecoder",
    "LinkResolution",
    "resolve_pin_links",
    "project_blueprint_graph",
    "project_k2_metadata",
    "project_opaque",
    "project_pin_link",
]

_K2_CLASSES = frozenset(
    {
        "K2Node_CallFunction",
        "K2Node_Event",
        "K2Node_VariableGet",
        "K2Node_VariableSet",
        "K2Node_CustomEvent",
        "K2Node_AddDelegate",
        "K2Node_RemoveDelegate",
        "K2Node_CallDelegate",
        "K2Node_IfThenElse",
    }
)


def _node_id_from_str(value: str) -> NodeId:
    if "/" in value:
        owner, node = value.split("/", 1)
        return NodeId(owner_object_id=owner, node_export_id=node)
    return NodeId(owner_object_id=value, node_export_id=value)


def resolve_pin_links(nodes: list[BlueprintNode], refs: list[PinLinkRef]) -> LinkResolution:
    """Resolve raw pin refs against owner-aware nodes.

    Lookup uses ``(owner_node_id, pin_guid)`` first. A GUID-only fallback runs
    only when the owner is unavailable and exactly one candidate carries the
    GUID. Ambiguous/unresolved refs become diagnostics — never an arbitrary
    last duplicate.
    """
    by_owner_guid: dict[tuple[str, str], list[tuple[str, str]]] = {}
    by_guid: dict[str, list[tuple[str, str]]] = {}
    for node in nodes:
        for pin in node.pins:
            if not pin.id:
                continue
            entry = (str(node.id), pin.id)
            by_owner_guid.setdefault((str(node.id), pin.id), []).append(entry)
            by_guid.setdefault(pin.id, []).append(entry)
    by_owner_guid = {k: list(dict.fromkeys(v)) for k, v in by_owner_guid.items()}
    by_guid = {k: list(dict.fromkeys(v)) for k, v in by_guid.items()}

    links: list[PinLink] = []
    diagnostics: list[Diagnostic] = []
    for ref in refs:
        owner_key = str(ref.to_owner_node_id) if ref.to_owner_node_id else None
        target: tuple[str, str] | None = None
        if owner_key is not None:
            candidates = by_owner_guid.get((owner_key, ref.to_pin_guid), [])
            if len(candidates) == 1:
                target = candidates[0]
            else:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="BLUEPRINT_PIN_LINK_UNRESOLVED",
                        message=(
                            f"pin link target {owner_key}/{ref.to_pin_guid} "
                            f"({len(candidates)} candidate(s))"
                        ),
                        stage="semantic.blueprint",
                    )
                )
                continue
        else:
            candidates = by_guid.get(ref.to_pin_guid, [])
            if len(candidates) == 1:
                target = candidates[0]
            else:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="BLUEPRINT_PIN_LINK_AMBIGUOUS" if len(candidates) > 1 else "BLUEPRINT_PIN_LINK_UNRESOLVED",
                        message=(
                            f"pin link guid {ref.to_pin_guid} has {len(candidates)} candidate(s) "
                            "without owner identity"
                        ),
                        stage="semantic.blueprint",
                        effect="semantic_loss",
                    )
                )
                continue
        links.append(
            PinLink(
                from_node_id=ref.from_node_id,
                from_pin_id=ref.from_pin_guid,
                to_node_id=_node_id_from_str(target[0]),
                to_pin_id=target[1],
                raw_ref=ref,
            )
        )
    return LinkResolution(links=links, diagnostics=diagnostics)


def _pin_from_raw(node_id: NodeId, pin: dict[str, Any]) -> BlueprintPin:
    linked: list[PinLink] = []
    for link in pin.get("linked") or []:
        to_node = link.get("to_node") or ""
        to_pin = link.get("to_pin") or ""
        if not to_node or not to_pin:
            continue
        raw = PinLinkRef(
            from_node_id=node_id,
            from_pin_guid=str(pin.get("id") or ""),
            to_owner_node_id=_node_id_from_str(to_node) if to_node else None,
            to_pin_guid=str(to_pin),
        )
        linked.append(
            PinLink(
                from_node_id=node_id,
                from_pin_id=str(pin.get("id") or ""),
                to_node_id=_node_id_from_str(to_node),
                to_pin_id=str(to_pin),
                raw_ref=raw,
            )
        )
    unknown: list[ByteRegion] = []
    for key in ("unknown_properties", "opaque"):
        for item in pin.get(key) or []:
            if isinstance(item, dict) and item.get("size") is not None:
                unknown.append(
                    ByteRegion(
                        start=int(item.get("start") or 0),
                        size=int(item.get("size") or 0),
                        status="opaque",
                        source_id=str(item.get("source_id") or "package"),
                        source_start=item.get("source_start"),
                        reason=item.get("reason") or "pin_unknown",
                        feature=str(item.get("feature") or "pin"),
                    )
                )
    return BlueprintPin(
        id=str(pin.get("id") or ""),
        name=str(pin.get("name") or ""),
        direction=str(pin.get("direction") or ""),
        category=str(pin.get("category") or ""),
        subcategory=str(pin.get("subcategory") or pin.get("sub_category") or ""),
        default_value=pin.get("default_value"),
        default_object_ref=pin.get("default_object_ref"),
        default_text=pin.get("default_text"),
        sub_pin_ids=[str(x) for x in (pin.get("sub_pin_ids") or [])],
        parent_pin_id=pin.get("parent_pin_id"),
        reference_pass_through_pin_id=pin.get("reference_pass_through_pin_id"),
        linked=linked,
        owner_node_id=node_id,
        raw_region=None,
        unknown_properties=unknown,
        is_const=bool(pin.get("is_const") or False),
        is_weak_pointer=bool(pin.get("is_weak_pointer") or False),
        is_uobject_wrapper=bool(pin.get("is_uobject_wrapper") or False),
    )


def _node_export_object_id(raw_id: Any) -> str:
    """Extract the node export id from raw/projected node ids.

    Raw decode nodes use ``export:N``; projected re-decode nodes use the
    NodeId string ``owner/export:N``. Returns ``""`` when unresolvable.
    """
    if not isinstance(raw_id, str) or not raw_id:
        return ""
    part = raw_id.rsplit("/", 1)[-1]
    return part if part.startswith("export:") or part.startswith("import:") else ""


def _object_name_index(objects_by_id: dict[str, Any] | None) -> dict[str, str]:
    if not objects_by_id:
        return {}
    return {
        obj_id: str(obj.name)
        for obj_id, obj in objects_by_id.items()
        if obj is not None and getattr(obj, "name", None)
    }


def _metadata_for(
    class_name: str,
    node: dict[str, Any],
    objects_by_id: dict[str, Any] | None = None,
) -> K2NodeMetadata | None:
    if class_name not in _K2_CLASSES and not class_name.startswith("K2Node_"):
        # Still attach metadata for allowlisted K2 classes only; other nodes
        # keep None so callers can distinguish "no K2 identity".
        if class_name not in _K2_CLASSES:
            return None
    from uasset_read.models.analysis import k2_metadata_from_dict
    from uasset_read.serializers.k2_metadata import K2MetadataDecoder

    existing = None
    raw_meta = node.get("metadata")
    if isinstance(raw_meta, dict) and raw_meta.get("node_class"):
        existing = k2_metadata_from_dict(raw_meta)

    node_record = None
    if objects_by_id:
        export_id = _node_export_object_id(node.get("id"))
        if export_id:
            node_record = objects_by_id.get(export_id)
    node_properties = getattr(node_record, "properties", None) if node_record is not None else None

    return K2MetadataDecoder().decode(
        None,
        None,
        node_class=class_name,
        node_data=node.get("node_data"),
        node_properties=node_properties,
        existing_metadata=existing,
        object_names=_object_name_index(objects_by_id),
    )


def _node_from_raw(
    owner_id: NodeId,
    node: dict[str, Any],
    objects_by_id: dict[str, Any] | None = None,
) -> BlueprintNode:
    node_export = str(node.get("id") or "")
    node_id = NodeId(owner_object_id=owner_id.owner_object_id, node_export_id=node_export or "export:-1")
    class_name = str(node.get("type") or node.get("class_name") or "")
    pins = [_pin_from_raw(node_id, p) for p in node.get("pins") or []]
    unknown: list[ByteRegion] = []
    for item in node.get("unknown_properties") or []:
        if isinstance(item, dict) and item.get("size") is not None:
            unknown.append(
                ByteRegion(
                    start=int(item.get("start") or 0),
                    size=int(item.get("size") or 0),
                    status="opaque",
                    source_id=str(item.get("source_id") or "package"),
                    source_start=item.get("source_start"),
                    reason=item.get("reason") or "node_unknown",
                    feature=str(item.get("feature") or "node"),
                )
            )
    return BlueprintNode(
        id=node_id,
        guid=node.get("node_guid") or node.get("guid"),
        class_name=class_name,
        title=str(node.get("name") or node.get("title") or class_name),
        metadata=_metadata_for(class_name, node, objects_by_id),
        pins=pins,
        raw_region=None,
        unknown_properties=unknown,
    )


def _parse_export_id(value: str) -> int | None:
    if not isinstance(value, str) or ":" not in value:
        return None
    try:
        return int(value.split(":", 1)[1])
    except ValueError:
        return None


def _graph_kind(name: str, graph_id: str, function_graph_ids: set[str]) -> BlueprintGraph["kind"]:
    if name == "EventGraph":
        return "event_graph"
    if name == "UserConstructionScript":
        return "construction_script"
    if graph_id in function_graph_ids:
        return "function"
    if "State" in name:
        # state_machine maps to unknown in IR Literal until extended
        return "unknown"
    # Prefer known IR literals from the plan; state machines are "unknown" until
    # the kind Literal is widened (handler still records state_machines separately).
    if name.endswith("Graph") and "Function" in name:
        return "function"
    return "unknown"


def _function_graph_ids(properties: Any) -> set[str]:
    if properties is None:
        return set()
    getter = getattr(properties, "get", None)
    if not callable(getter):
        return set()
    entry = getter("FunctionGraphs")
    value = entry.get("value") if isinstance(entry, dict) else None
    if isinstance(entry, dict) and value is None:
        # PropertyBag.get may already return the value.
        value = entry if isinstance(entry, list) else None
    if not isinstance(value, list):
        # try bag.get returning PropertyEntry
        if hasattr(entry, "value"):
            value = getattr(entry, "value", None)
    if not isinstance(value, list):
        return set()
    ids: set[str] = set()
    for item in value:
        if isinstance(item, int) and item > 0:
            ids.add(f"export:{item - 1}")
        elif isinstance(item, str) and item.startswith("export:"):
            ids.add(item)
    return ids


class BlueprintGraphDecoder:
    """Convert package graph exports into typed owner-aware IR.

    Prefers graphs already attached under ``obj.semantic["graphs"]`` (or the
    extras channel produced by the package read). Falls back to opening the
    package source only when no attached raw graphs exist. Never reopens a
    closed document for a second binary parse when projection data is present.
    """

    def decode(
        self,
        obj: ObjectRecord,
        document: PackageDocument,
        *,
        source: ByteSource | None = None,
    ) -> list[BlueprintGraph]:
        raw_list = self._raw_graphs_for(obj, document, source=source)
        function_ids = _function_graph_ids(obj.properties)
        owner_num = _parse_export_id(obj.id)
        objects_by_id = {o.id: o for o in document.objects}
        graphs: list[BlueprintGraph] = []
        for raw in raw_list:
            if not isinstance(raw, dict):
                continue
            graph_num = _parse_export_id(str(raw.get("id") or ""))
            owner_for_nodes = NodeId(
                owner_object_id=obj.id,
                node_export_id=obj.id,
            )
            # Node owner is the Blueprint export that owns this graph.
            nodes = []
            refs: list[PinLinkRef] = []
            for node_raw in raw.get("nodes") or []:
                node = _node_from_raw(owner_for_nodes, node_raw, objects_by_id)
                nodes.append(node)
                for pin in node.pins:
                    for link in pin.linked:
                        refs.append(link.raw_ref)
            # Rebuild links through the typed resolver for diagnostics parity.
            resolution = resolve_pin_links(nodes, refs)
            # Re-attach resolved links (already on pins) and keep diagnostics.
            parse_errors = [str(e) for e in raw.get("parse_errors") or []]
            truncated = bool((raw.get("truncated") or {}).get("nodes") or (raw.get("truncated") or {}).get("pins"))
            kind = _graph_kind(str(raw.get("name") or ""), str(raw.get("id") or ""), function_ids)
            graphs.append(
                BlueprintGraph(
                    id=GraphId(
                        owner_export_index=owner_num if owner_num is not None else -1,
                        graph_export_index=graph_num if graph_num is not None else -1,
                    ),
                    name=str(raw.get("name") or ""),
                    kind=kind,  # type: ignore[arg-type]
                    nodes=nodes,
                    parse_errors=parse_errors + [d.message for d in resolution.diagnostics],
                    raw_region=None,
                    truncated=truncated,
                )
            )
        return graphs

    def _raw_graphs_for(
        self,
        obj: ObjectRecord,
        document: PackageDocument,
        *,
        source: ByteSource | None,
    ) -> list[dict[str, Any]]:
        semantic = obj.semantic if isinstance(obj.semantic, dict) else {}
        attached = semantic.get("graphs")
        if isinstance(attached, list) and attached:
            return [g for g in attached if isinstance(g, dict)]
        if source is None:
            return []
        return self._read_from_source(source, obj, document)

    def _read_from_source(
        self,
        source: ByteSource,
        obj: ObjectRecord,
        document: PackageDocument,
    ) -> list[dict[str, Any]]:
        """Open the package archive once and read graphs owned by ``obj``."""
        from uasset_read.package import open_package_bundle
        from uasset_read.serializers.blueprint_graph import read_blueprint_graphs
        from uasset_read.serializers.object_resources import read_export_map, read_import_map
        from uasset_read.serializers.package_summary import read_name_table, read_package_summary

        path = self._package_path(source, document)
        if path is None:
            return []
        archive = open_package_bundle(str(path)).open_archive(tolerant=True)
        try:
            summary, _ = read_package_summary(archive)
            name_map = read_name_table(archive, summary)
            archive.set_name_map(name_map)
            import_map = read_import_map(archive, summary, name_map)
            export_map = read_export_map(archive, summary, name_map)
            graphs = read_blueprint_graphs(archive, summary, name_map, import_map, export_map)
        finally:
            archive.close()
        # Filter to graphs whose outer chain reaches this owner (best effort).
        owner_num = _parse_export_id(obj.id)
        if owner_num is None:
            return graphs
        kept: list[dict[str, Any]] = []
        for g in graphs:
            gnum = _parse_export_id(str(g.get("id") or ""))
            if gnum is None:
                continue
            if self._outer_reaches(export_map, gnum, owner_num):
                kept.append(g)
        return kept

    @staticmethod
    def _outer_reaches(export_map: Any, start: int, target: int, limit: int = 64) -> bool:
        idx = start
        for _ in range(limit):
            if idx == target:
                return True
            if idx < 0 or idx >= len(export_map):
                return False
            outer = getattr(export_map[idx], "outer_index", None)
            outer_idx = getattr(outer, "index", 0) if outer is not None else 0
            if outer_idx <= 0:
                return False
            idx = outer_idx - 1
        return False

    @staticmethod
    def _package_path(source: ByteSource, document: PackageDocument) -> Path | None:
        info = getattr(source, "describe", None)
        described = info() if callable(info) else None
        path_attr = getattr(described, "path", None) if described is not None else None
        if path_attr:
            candidate = Path(path_attr)
            if candidate.exists():
                return candidate
        segments = getattr(source, "segments", None)
        if callable(segments):
            for name, _start, _size in segments():
                # Prefer main package file name from document source.
                break
        doc_path = getattr(document.source, "path", None) if document.source else None
        if doc_path:
            candidate = Path(doc_path)
            if candidate.exists():
                return candidate
        return None
