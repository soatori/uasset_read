"""Allow-listed tag-derived node_data projection (no binary readers).

Shared by the Anim full-context path and the K2Node/tag projection path.
Wave A removed K2Node / FMemberReference binary readers and the unused
``FMemberReference`` model; only primitives already present on raw
script-serial tags survive here.
"""

from __future__ import annotations

from typing import Any

# Allow-list of tag-derived node_data keys emitted onto decode nodes.
# Private bookkeeping (leading "_") is never emitted. Opaque tag locators
# ({size, offset} only) are never emitted under these keys.
NODE_DATA_ALLOW = frozenset(
    {
        "FunctionReference",
        "EventReference",
        "MemberName",
        "MemberParent",
        "VariableReference",
        "SelfContextInfo",
        "FunctionName",
        "CustomFunctionName",
        "subgraph_references",
        "bDefaultsToPure",
        "bDefaultsToPureFunc",
        "InputActionShortName",
        "OperationName",
        "TimelineName",
    }
)


def is_opaque_tag_locator(value: Any) -> bool:
    """True for unmatched-tag locators ``{size, offset}`` only (no member identity)."""
    return isinstance(value, dict) and bool(value) and set(value.keys()) <= {"size", "offset"}


def project_node_data(node_data: Any) -> dict[str, Any] | None:
    """Project allow-listed tag-derived keys onto a plain dict.

    Never invents binary readers: only primitives (and nested primitive maps)
    already present on ``node_data`` survive. Opaque tag locators
    (``{size, offset}`` only) are omitted so keys like ``VariableReference``
    never pretend to carry member identity. ``None`` means nothing projectable
    — omit the key.
    """
    if not isinstance(node_data, dict):
        return None
    out: dict[str, Any] = {}
    for key, value in node_data.items():
        if not isinstance(key, str) or key.startswith("_"):
            continue  # never emit private bookkeeping
        if key not in NODE_DATA_ALLOW:
            continue
        if is_opaque_tag_locator(value):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
        elif key == "subgraph_references" and isinstance(value, dict):
            # Anim subgraph_references: {name: {package_index, object_name, ...}}
            compact: dict[str, Any] = {}
            for ref_key, info in value.items():
                if isinstance(info, dict):
                    prims = {
                        k: v
                        for k, v in info.items()
                        if isinstance(v, (str, int, float, bool, type(None)))
                    }
                    if prims:
                        compact[str(ref_key)] = prims
            if compact:
                out[key] = compact
        elif isinstance(value, dict):
            prims = {
                k: v for k, v in value.items() if isinstance(v, (str, int, float, bool, type(None)))
            }
            if prims:
                out[key] = prims
    return out or None
