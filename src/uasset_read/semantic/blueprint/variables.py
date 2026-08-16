"""Variables and declaration index (BP-§13, #551 P0 declaration layer)."""
from __future__ import annotations

from typing import Any

_REPLICATION_CONDITIONS = {
    0: "always", 1: "initial_only", 2: "initial_or_ongoing", 3: "owner_only",
}

_PRIMITIVES = {"bool", "int", "int64", "float", "double", "string", "name",
               "text", "byte", "object", "vector", "rotator", "transform"}


def emit_variables(variables, table, reporting) -> list[dict]:
    """Emit the ``variables`` array from VariableIR facts."""
    out: list[dict] = []
    for var in variables or []:
        if getattr(var, "kind", "user") in ("metadata", "input_action"):
            continue  # internal engine entries are not Blueprint variables (BP-§13)
        entry: dict[str, Any] = {"name": getattr(var, "name", "") or ""}
        var_type = (getattr(var, "type", "") or "").strip()
        entry["type"] = _type_for(var_type, table)
        default = getattr(var, "default_value", None)
        if default not in (None, ""):
            entry["default"] = _coerce_default(var_type, default)
        flags = sorted(getattr(var, "flags_labels", None) or [])
        if flags:
            entry["flags"] = flags
        guid = getattr(var, "guid", None)
        if guid:
            entry["identity"] = guid
        category = getattr(var, "category", "") or ""
        if category and category != "Default":
            entry["category"] = category
        replication: dict[str, Any] = {}
        if getattr(var, "is_replicated", False):
            replication["condition"] = _REPLICATION_CONDITIONS.get(
                getattr(var, "replication_condition", 0), "unknown")
            notify = getattr(var, "rep_notify_func", "") or ""
            if notify and "RepNotify" in flags:
                replication["notify"] = notify
        if replication:
            entry["replication"] = replication
        out.append(entry)

    reporting.coverage("variables", "partial", reason="cdo_and_inheritance_not_resolved")
    return out


def emit_declaration(variable_names, component_ids, functions, parent_class, interfaces) -> dict:
    """Declaration index — references only, no duplicated facts (#551 P0)."""
    decl: dict[str, Any] = {}
    if parent_class:
        decl["parent_class"] = parent_class
    if interfaces:
        decl["interfaces"] = sorted(interfaces)
    func_entries = []
    for fn in functions or []:
        item: dict[str, Any] = {"name": fn.get("name", "")}
        if fn.get("graph"):
            item["graph"] = fn["graph"]
        func_entries.append(item)
    if func_entries:
        decl["functions"] = func_entries
    if variable_names:
        decl["variables"] = sorted(variable_names)
    if component_ids:
        decl["components"] = sorted(component_ids)
    return decl


def _type_for(type_str: str, table) -> Any:
    lowered = type_str.lower()
    if lowered in _PRIMITIVES:
        return lowered
    if not type_str:
        return "unknown"
    return table.type_ref_for(category="unknown", subcategory=type_str)


def _coerce_default(type_str: str, raw: Any) -> Any:
    lowered = (type_str or "").lower()
    if not isinstance(raw, str):
        return raw
    if lowered == "bool":
        return raw.strip().lower() == "true"
    if lowered in ("int", "int64", "byte"):
        try:
            return int(raw)
        except ValueError:
            return raw
    if lowered in ("float", "double"):
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw
