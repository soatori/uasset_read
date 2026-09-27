"""Version-gated K2 node member/event/variable/dispatcher metadata.

Narrow boundary only: identity comes from already-projected tag identity on
``node_data`` and from the node export's ``ObjectRecord.properties``
(``EventReference`` / ``FunctionReference`` / ``VariableReference`` structs).
Remaining node fields stay owned by ``graph_node.py``. Gates key off package
custom versions — never a UE major-version shortcut.
"""

from __future__ import annotations

from typing import Any

from uasset_read.models.analysis import K2NodeMetadata

# Tag-derived identity keys already projected onto node_data by graph_node.
_IDENTITY_KEYS = (
    ("function_name", ("FunctionName", "CustomFunctionName", "FunctionReference")),
    ("event_name", ("EventName", "EventReference")),
    ("variable_name", ("VariableName", "MemberName", "VariableReference")),
    ("dispatcher_name", ("DispatcherName",)),
    ("member_parent", ("MemberParent",)),
)

# Export-level property keys that carry FMemberReference-style identity.
_REFERENCE_PROP_KEYS = ("EventReference", "FunctionReference", "VariableReference")

_IDENTITY_FIELD_NAMES = (
    "function_name",
    "event_name",
    "variable_name",
    "dispatcher_name",
    "member_parent",
)


def _member_fields(value: Any) -> dict[str, Any] | None:
    """Unwrap a normalized MemberReference struct / plain mapping / name string."""
    if isinstance(value, str) and value:
        return {"MemberName": value}
    if not isinstance(value, dict) or not value:
        return None
    if value.get("kind") == "struct" and isinstance(value.get("fields"), dict):
        return value["fields"]
    return value


def _extract_name(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    fields = _member_fields(value)
    if fields is None:
        return None
    for key in ("MemberName", "name", "member_name", "function_name", "event_name"):
        inner = fields.get(key)
        if isinstance(inner, str) and inner:
            return inner
    return None


def _extract_parent(value: Any, object_names: dict[str, str] | None = None) -> str | None:
    """MemberParent as a display string: resolved object name or package-index id."""
    fields = _member_fields(value)
    if fields is None:
        return None
    raw = fields.get("MemberParent")
    if isinstance(raw, str) and raw:
        return raw
    if isinstance(raw, int) and raw != 0:
        object_id = f"import:{-raw - 1}" if raw < 0 else f"export:{raw - 1}"
        if object_names:
            name = object_names.get(object_id)
            if name:
                return name
        return object_id
    return None


def _identity_from_node_data(
    node_class: str,
    node_data: Any,
    object_names: dict[str, str] | None = None,
) -> K2NodeMetadata:
    meta = K2NodeMetadata(node_class=node_class)
    if isinstance(node_data, dict):
        for field_name, keys in _IDENTITY_KEYS:
            for key in keys:
                if key not in node_data:
                    continue
                if field_name == "member_parent":
                    extracted = _extract_parent(node_data[key], object_names)
                else:
                    extracted = _extract_name(node_data[key])
                if extracted:
                    setattr(meta, field_name, extracted)
                    break
    return meta


def _enrich_identity(
    meta: K2NodeMetadata,
    node_properties: Any,
    object_names: dict[str, str] | None = None,
) -> None:
    """Fill empty identity slots from the node export's property bag."""
    if node_properties is None:
        return
    getter = getattr(node_properties, "get", None)
    if not callable(getter):
        return

    # Plain tag keys first (EventName / MemberName / ...).
    for field_name, keys in _IDENTITY_KEYS:
        for key in keys:
            value = getter(key)
            if value is None:
                continue
            if field_name == "member_parent":
                extracted = _extract_parent(value, object_names)
            else:
                extracted = _extract_name(value)
            if extracted:
                setattr(meta, field_name, extracted)
                break

    # FMemberReference structs (EventReference / FunctionReference / ...).
    for ref_key in _REFERENCE_PROP_KEYS:
        raw = getter(ref_key)
        fields = _member_fields(raw)
        if not fields:
            continue
        name = _extract_name(fields)
        if name:
            if ref_key == "EventReference" and not meta.event_name:
                meta.event_name = name
            elif ref_key == "FunctionReference" and not meta.function_name:
                meta.function_name = name
            elif ref_key == "VariableReference" and not meta.variable_name:
                meta.variable_name = name
        parent = _extract_parent(fields, object_names)
        if parent and not meta.member_parent:
            meta.member_parent = parent
        if meta.member_reference is None:
            prims = {
                str(k): v
                for k, v in fields.items()
                if isinstance(v, (str, int, float, bool, type(None)))
            }
            if prims:
                meta.member_reference = prims


def _merge_identity(target: K2NodeMetadata, source: K2NodeMetadata) -> None:
    for field_name in _IDENTITY_FIELD_NAMES:
        if not getattr(target, field_name) and getattr(source, field_name):
            setattr(target, field_name, getattr(source, field_name))
    if target.member_reference is None and source.member_reference is not None:
        target.member_reference = source.member_reference


def decode_k2_metadata(
    *,
    node_class: str,
    node_data: Any = None,
    node_properties: Any = None,
    existing_metadata: K2NodeMetadata | None = None,
    object_names: dict[str, str] | None = None,
) -> K2NodeMetadata:
    """Decode K2 member/event/variable metadata for known node classes.

    Prefers already-projected tag identity on ``node_data`` (populated by
    ``graph_node`` script_serial tags), then the node export's property bag
    (``EventReference`` / ``FunctionReference`` structs), then any pre-existing
    projected ``existing_metadata``.
    """
    if existing_metadata is not None:
        meta = existing_metadata
        if not meta.node_class and node_class:
            meta.node_class = node_class
    else:
        meta = K2NodeMetadata(node_class=node_class)

    _merge_identity(meta, _identity_from_node_data(node_class, node_data, object_names))
    _enrich_identity(meta, node_properties, object_names)
    return meta
