"""Components emission (BP-§14).

v1 provenance scope: origin is scs_owned/scs_inherited/native only when an
explicit evidence key is present in the source dict; otherwise 'unverified'
with partial coverage. Parent/socket come from the source dict only.
"""
from __future__ import annotations

from typing import Any


def emit_components(source_components, table, reporting) -> list[dict]:
    by_name: dict[str, int] = {}
    pending_parent: list[tuple[dict, str, int]] = []
    out: list[dict] = []
    for idx, comp in enumerate(source_components or []):
        name = str(comp.get("name") or f"Component{idx}")
        entry: dict[str, Any] = {"id": f"c{len(out)}", "name": name}
        cls = comp.get("class") or comp.get("component_class") or ""
        if cls:
            entry["type"] = table.type_ref_for(category="class", subcategory_object_name=str(cls))
        entry["origin"] = _origin(comp)
        socket = comp.get("socket") or comp.get("attach_socket_name")
        if socket:
            entry["socket"] = str(socket)
        transform = comp.get("transform")
        if isinstance(transform, dict) and transform:
            entry["transform"] = transform
        parent_name = comp.get("parent") or comp.get("attach_parent")
        by_name[name] = len(out)
        if parent_name:
            pending_parent.append((entry, str(parent_name), len(out)))
        out.append(entry)

    for entry, parent_name, self_idx in pending_parent:
        parent_idx = by_name.get(parent_name)
        if parent_idx is not None and parent_idx != self_idx:
            entry["parent"] = f"c{parent_idx}"
        else:
            reporting.diagnostic("BP_COMPONENT_PARENT_UNRESOLVED", "components",
                                 "warning", "semantic_loss",
                                 occurrence={"component": entry["name"], "parent": parent_name})

    if out:
        reporting.coverage("components", "partial", reason="scs_origin_not_fully_verified")
    return out


def _origin(comp: dict) -> str:
    if comp.get("scs_node") or comp.get("from_scs"):
        return "scs_owned"
    if comp.get("inherited_override"):
        return "scs_inherited"
    if comp.get("native"):
        return "native"
    return "unverified"
