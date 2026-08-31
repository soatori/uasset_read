"""Blueprint graph construction utility functions.

Shared helper functions extracted from flow_builder.py: string sanitization,
Pin reference formatting, node index building, connection traversal, etc.
"""

from typing import Dict, List, Optional, Tuple, Set, Any, Iterable

from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin


def _normalize_pin_id(v):
    """Normalize pin GUID: strip dashes, lowercase."""
    return v.replace("-", "").lower() if v else v


# ============================================================================
# String sanitization
# ============================================================================


def _sanitize_string(value: str) -> str:
    """Sanitize binary/null characters from strings to ensure JSON-safe output.

    Preserves common control characters like \n \r \t, removes null and other control characters.
    """
    if not value:
        return value
    # Remove null characters
    value = value.replace("\x00", "")
    # Remove other control characters (preserve \n \r \t)
    value = "".join(c for c in value if c >= " " or c in "\n\r\t")
    return value


def _sanitize_pin_dict(pin_dict: dict) -> dict:
    """Sanitize all string fields in a pin dict."""
    sanitized = {}
    for key, val in pin_dict.items():
        if isinstance(val, str):
            sanitized[key] = _sanitize_string(val)
        elif isinstance(val, (list, dict)):
            sanitized[key] = _sanitize_recursive(val)
        else:
            sanitized[key] = val
    return sanitized


def _sanitize_recursive(obj, visited=None):
    """Recursively sanitize strings in lists/dictionaries.

    Args:
        obj: object to sanitize
        visited: set of visited object ids, used to prevent infinite recursion from circular references
    """
    # Initialize visited set (only on top-level call)
    if visited is None:
        visited = set()

    # Check circular references for mutable objects
    if isinstance(obj, (list, dict)):
        obj_id = id(obj)
        if obj_id in visited:
            # Circular reference detected, return safe replacement value
            if isinstance(obj, dict):
                return {}
            return []
        visited.add(obj_id)

    if isinstance(obj, str):
        return _sanitize_string(obj)
    elif isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    elif isinstance(obj, list):
        return [_sanitize_recursive(item, visited) for item in obj]
    elif isinstance(obj, dict):
        return {k: _sanitize_recursive(v, visited) for k, v in obj.items()}
    elif hasattr(obj, "get_full_name"):
        try:
            return obj.get_full_name()
        except Exception:
            return str(obj)
    elif hasattr(obj, "object_name"):
        return getattr(obj, "object_name", str(obj))
    return str(obj)


# ============================================================================
# Pin reference and GUID utilities
# ============================================================================


def _pin_ref_guid(ref: object) -> str | None:
    """Extract pin guid from LinkedTo/PinReference structures (normalized to 32-char lowercase hex).

    PinReference GUID raw format is 8-4-4-4-12 with dashes (_read_guid output),
    and normalization aligns with pin_id (.hex() output) format, ensuring connection lookup matches.
    """
    raw_guid: str | None = None
    if isinstance(ref, dict):
        raw_guid = ref.get("pin_guid") or ref.get("pin_id")
    elif isinstance(ref, str):
        raw_guid = ref
    else:
        raw_guid = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)

    if not raw_guid:
        return None

    # Normalize: remove dashes, convert to lowercase
    return _normalize_pin_id(raw_guid)


def _pin_direction_text(direction: int) -> str:
    """Return stable pin direction text for Blueprint DTO output."""
    return "output" if direction == 1 else "input"


def _pin_category(pin: UEdGraphPin) -> str:
    return pin.pin_type.pin_category if pin.pin_type else ""


def _pin_subcategory(pin: UEdGraphPin) -> str:
    return pin.pin_type.pin_subcategory if pin.pin_type else ""


def _pin_container_type(pin: UEdGraphPin) -> str:
    if not pin.pin_type:
        return ""
    return str(getattr(pin.pin_type, "container_type", "") or "")


def _is_exec_pin(pin: UEdGraphPin) -> bool:
    return bool(pin.pin_type and pin.pin_type.pin_category == "exec")


def _is_valid_pin_guid(guid: object) -> bool:
    """Validate Pin GUID validity.

    Supports multiple formats:
    - 32-char pure hex (pin_id format)
    - 36-char hex with dashes (PinReference format, e.g. A1B2C3D4-E5F6-...)
    - "pin-" prefix (test fixture)
    - all-zero GUID (ParentPin empty reference)
    """
    if not isinstance(guid, str) or not guid:
        return False

    # Test fixture compatibility
    if guid.startswith("pin-"):
        return True

    # Normalize: remove dashes, convert to lowercase
    normalized = _normalize_pin_id(guid)

    # All-zero GUID (valid empty reference)
    if normalized == "0" * 32:
        return True

    # Validate 32-char hex (normalized is lowercase)
    if len(normalized) != 32:
        return False

    return all(c in "0123456789abcdef" for c in normalized)


# ============================================================================
# Node names and indices
# ============================================================================


def _derive_node_name(node: UEdGraphNode, idx: int) -> str:
    """Derive a user-friendly node name from the node (D-19-02).

    Strategy: use f"{class_name}_{idx}" format to avoid conflicts with same-named nodes.
    """
    return f"{node.class_name}_{idx}"


def format_pin_ref(node_guid: str, pin_name: str, node_name_lookup: Dict[str, str]) -> Dict:
    """Format a Pin reference as a node-name lookup (D-19-02, D-19-05).

    Args:
        node_guid: node GUID
        pin_name: Pin name
        node_name_lookup: node_guid -> node_name lookup table

    Returns:
        Dict: formatted Pin reference object
    """
    if node_guid in node_name_lookup:
        return {"node": node_name_lookup[node_guid], "pin": pin_name}
    return {"node_guid": node_guid, "pin": pin_name, "warning": "node_name lookup failed"}


def _format_blueprint_pin_dto(
    pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_name_lookup: Dict[str, str],
) -> Dict[str, Any]:
    """Format a pin using the compact Blueprint DTO shape."""
    linked_to: List[str] = []
    for ref in pin.linked_to_raw or []:
        target_pin_id = _pin_ref_guid(ref)
        if target_pin_id in pin_lookup:
            target_node_guid, target_pin_name = pin_lookup[target_pin_id]
            target_node_name = node_name_lookup.get(target_node_guid, target_node_guid)
            linked_to.append(f"{target_node_name}.{target_pin_name}")
        elif target_pin_id:
            linked_to.append(str(target_pin_id))
        elif isinstance(ref, dict) and ref.get("owning_node"):
            linked_to.append(str(ref["owning_node"]))

    pin_type = pin.pin_type
    return {
        "PinId": pin.persistent_guid or pin.pin_id,
        "PinName": pin.pin_name,
        "Direction": _pin_direction_text(pin.direction),
        "PinCategory": _pin_category(pin),
        "PinSubCategory": _pin_subcategory(pin),
        "DefaultValue": pin.default_value,
        "LinkedTo": linked_to,
        "IsReference": bool(getattr(pin_type, "is_reference", False)) if pin_type else False,
        "IsConst": bool(getattr(pin_type, "is_const", False)) if pin_type else False,
        "ContainerType": _pin_container_type(pin),
    }


# ============================================================================
# Graph index building
# ============================================================================


def _build_graph_indexes(
    graph: UEdGraph,
) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, UEdGraphNode], Dict[str, UEdGraphPin]]:
    """Build node and Pin lookup tables.

    Pin keys are uniformly normalized to lowercase hex (aligned with _pin_ref_guid output format),
    preventing connection lookup failures due to case inconsistency.
    """
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    node_lookup: Dict[str, UEdGraphNode] = {}
    pin_object_lookup: Dict[str, UEdGraphPin] = {}
    for node in graph.nodes:
        node_lookup[node.node_guid] = node
        for pin in node.pins:
            normalized_key = _normalize_pin_id(pin.pin_id)
            pin_lookup[normalized_key] = (node.node_guid, pin.pin_name)
            pin_object_lookup[normalized_key] = pin
    return pin_lookup, node_lookup, pin_object_lookup


def _node_member_name(node: Optional[UEdGraphNode]) -> str:
    if node is None or not node.node_data:
        return ""
    ref = None
    if isinstance(node.node_data, dict):
        ref = node.node_data.get("function_reference") or node.node_data.get("event_reference")
    else:
        ref = getattr(node.node_data, "function_reference", None) or getattr(node.node_data, "event_reference", None)
    if isinstance(ref, dict):
        return ref.get("member_name", "") or ""
    return getattr(ref, "member_name", "") or ""


def _choose_synthetic_source_pin(source_node: UEdGraphNode, target_node: UEdGraphNode, target_pin: UEdGraphPin) -> str:
    """Infer a readable source pin name when target LinkedTo only retains owning_node but source pin is unresolved."""
    target_category = target_pin.pin_type.pin_category if target_pin.pin_type else ""

    if target_category == "exec":
        if source_node.class_name == "K2Node_Event":
            return "then"
        if source_node.class_name == "K2Node_EnhancedInputAction":
            return "Triggered"

    return "Output"


def _iter_normalized_edges(
    graph: UEdGraph,
) -> Iterable[Dict[str, Any]]:
    """Iterate normalized connection edges.

    UE text-exported LinkedTo may appear on both input/output sides. The old implementation
    only scanned forward from output pins, missing many connections recorded on input pins
    in real assets. This helper uniformly outputs from(output) -> to(input), preserving
    raw direction for diagnostics.
    """
    pin_lookup, node_lookup, pin_object_lookup = _build_graph_indexes(graph)
    export_name_lookup: Dict[str, UEdGraphNode] = {}
    for node in graph.nodes:
        export_name = getattr(node, "_export_object_name", None)
        if export_name:
            export_name_lookup[export_name] = node

    def _resolve_owner_qualified_pin(
        ref: object,
        pin_id: Optional[str],
        current_direction: int,
    ) -> Optional[Tuple[UEdGraphNode, UEdGraphPin]]:
        """Resolve a LinkedTo pin within its declared owning node when unambiguous."""
        if not isinstance(ref, dict) or not pin_id:
            return None
        owner = export_name_lookup.get(ref.get("owning_node"))
        if owner is None:
            return None

        opposite_direction = 0 if current_direction == 1 else 1
        candidates = [
            candidate
            for candidate in owner.pins
            if (_normalize_pin_id(candidate.pin_id) == pin_id and candidate.direction == opposite_direction)
        ]
        if len(candidates) != 1:
            return None
        return owner, candidates[0]

    seen: Set[Tuple[str, str, str, str]] = set()

    def _emit(
        from_node: UEdGraphNode,
        from_pin_name: str,
        from_pin_id: str,
        from_pin_obj: Optional[UEdGraphPin],
        to_node: UEdGraphNode,
        to_pin_name: str,
        to_pin_id: str,
        to_pin_obj: Optional[UEdGraphPin],
    ) -> Optional[Dict[str, Any]]:
        key = (from_node.node_guid, from_pin_name, to_node.node_guid, to_pin_name)
        if key in seen:
            return None
        seen.add(key)

        category = ""
        if from_pin_obj and from_pin_obj.pin_type:
            category = from_pin_obj.pin_type.pin_category
        elif to_pin_obj and to_pin_obj.pin_type:
            category = to_pin_obj.pin_type.pin_category

        return {
            "from_node_guid": from_node.node_guid,
            "from_pin": from_pin_name,
            "from_pin_id": from_pin_id,
            "from_node": from_node,
            "from_pin_obj": from_pin_obj,
            "to_node_guid": to_node.node_guid,
            "to_pin": to_pin_name,
            "to_pin_id": to_pin_id,
            "to_node": to_node,
            "to_pin_obj": to_pin_obj,
            "pin_category": category,
            "is_exec": (
                (from_pin_obj is not None and _is_exec_pin(from_pin_obj))
                or (to_pin_obj is not None and _is_exec_pin(to_pin_obj))
                or category == "exec"
            ),
        }

    for node in graph.nodes:
        for pin in node.pins:
            for ref in pin.linked_to_raw or []:
                other_pin_id = _pin_ref_guid(ref)
                owner_qualified = _resolve_owner_qualified_pin(
                    ref,
                    other_pin_id,
                    pin.direction,
                )
                if owner_qualified is not None:
                    other_node, other_pin = owner_qualified
                    other_node_guid = other_node.node_guid
                    other_pin_name = other_pin.pin_name
                else:
                    other_pin = pin_object_lookup.get(other_pin_id) if other_pin_id else None
                    other_node_guid = ""
                    other_pin_name = ""

                if other_pin_id in pin_lookup and other_pin is not None:
                    if owner_qualified is None:
                        other_node_guid, other_pin_name = pin_lookup[other_pin_id]
                        other_node = node_lookup[other_node_guid]

                    if pin.direction == 1 and other_pin.direction == 0:
                        edge = _emit(
                            node,
                            pin.pin_name,
                            _normalize_pin_id(pin.pin_id),
                            pin,
                            other_node,
                            other_pin_name,
                            other_pin_id,
                            other_pin,
                        )
                    elif pin.direction == 0 and other_pin.direction == 1:
                        edge = _emit(
                            other_node,
                            other_pin_name,
                            other_pin_id,
                            other_pin,
                            node,
                            pin.pin_name,
                            _normalize_pin_id(pin.pin_id),
                            pin,
                        )
                    else:
                        edge = None
                    if edge:
                        yield edge
                    continue

                # Fallback: when PinId is not resolved, reconstruct from LinkedTo's owning_node
                # from owning node -> current input pin. This covers
                # Touch/EnhancedInput event edges and some parameter edges in UE text references.
                if pin.direction != 0 or not isinstance(ref, dict):
                    continue
                owning_node_name = ref.get("owning_node")
                source_node = export_name_lookup.get(owning_node_name)
                if not source_node:
                    continue

                source_pin_name = _choose_synthetic_source_pin(source_node, node, pin)
                source_pin_obj = next(
                    (p for p in source_node.pins if p.pin_name == source_pin_name),
                    None,
                )
                source_pin_id = (
                    _normalize_pin_id(source_pin_obj.pin_id)
                    if source_pin_obj is not None
                    else f"{source_node.node_guid}:{source_pin_name}"
                )
                edge = _emit(
                    source_node,
                    source_pin_name,
                    source_pin_id,
                    source_pin_obj,
                    node,
                    pin.pin_name,
                    _normalize_pin_id(pin.pin_id),
                    pin,
                )
                if edge:
                    yield edge


def _build_normalized_edge_indexes(
    graph: UEdGraph,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    """Return from_pin_id/to_pin_id bidirectional indices."""
    by_from: Dict[str, List[Dict[str, Any]]] = {}
    by_to: Dict[str, List[Dict[str, Any]]] = {}
    for edge in _iter_normalized_edges(graph):
        by_from.setdefault(edge["from_pin_id"], []).append(edge)
        by_to.setdefault(edge["to_pin_id"], []).append(edge)
    return by_from, by_to
