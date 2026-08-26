"""Graph/node/pin/port emission for Animation Blueprint semantic JSON.

Extends the Blueprint node emission with animation-specific node kinds:
- Pose nodes (input/output pose connections)
- State machine nodes
- Blend nodes
- Animation-specific nodes
"""
from __future__ import annotations

from uasset_read.semantic.blueprint.ids import ascii_slug
from uasset_read.semantic.blueprint.nodes import (
    _NODE_KIND_MAP,
    _graph_kind,
    _node_name,
    _direction_str,
    _is_exec,
    _linked_guids,
    _pin_keep,
)
from uasset_read.semantic.anim_blueprint.ids import (
    graph_id as ab_graph_id,
    node_id as ab_node_id,
    data_endpoint,
    exec_endpoint,
    pose_endpoint,
)
from uasset_read.semantic.blueprint.types import type_ref_from_pin


# Animation-specific node kinds
_ANIM_NODE_KIND_MAP = {
    "AnimNode_BlendListBase": "blend_list",
    "AnimNode_BlendListByBool": "blend_list",
    "AnimNode_BlendListByEnum": "blend_list",
    "AnimNode_BlendListByInt": "blend_list",
    "AnimNode_BlendListByFloat": "blend_list",
    "AnimNode_SequencePlayer": "sequence_player",
    "AnimNode_SequenceEvaluator": "sequence_evaluator",
    "AnimNode_StateMachine": "state_machine",
    "AnimNode_StateResult": "state_result",
    "AnimNode_Conduit": "conduit",
    "AnimNode_TransitionResult": "transition_result",
    "AnimNode_RandomPlayer": "random_player",
    "AnimNode_MultiBlendSpace": "blend_space",
    "AnimNode_BlendSpacePlayer": "blend_space_player",
    "AnimNode_Scale": "scale",
    "AnimNode_LayeredBlendPerBone": "layered_blend",
    "AnimNode_ModifyBone": "modify_bone",
    "AnimNode_CopyBone": "copy_bone",
    "AnimNode_ApplyMeshSpaceAdditive": "additive",
    "AnimNode_Root": "root",
    "AnimNode_SaveCachedPose": "save_cached_pose",
    "AnimNode_UseCachedPose": "use_cached_pose",
    "AnimNode_Mirror": "mirror",
    "AnimNode_Pose": "pose",
    "AnimNode_PoseByName": "pose_by_name",
    "AnimNode_Sync": "sync",
    "AnimNode_RotationOffsetBlendSpace": "rotation_offset",
    "AnimNode_TwoBoneIK": "two_bone_ik",
    "AnimNode_Fabrik": "fabrik",
    "AnimNode_SplineIK": "spline_ik",
    "AnimNode_ApplyAdditive": "apply_additive",
    "AnimNode_BlendBoneByChannel": "blend_bone",
    "AnimNode_OrientationConstraint": "orientation_constraint",
    "AnimNode_AimOffsetLookAt": "aim_offset",
    "AnimNode_SkeletalControlBase": "skeletal_control",
    "AnimNode_WheelHandler": "wheel_handler",
    "AnimNode_TwistBone": "twist_bone",
    "AnimNode_Trail": "trail",
    "AnimNode_SubInstance": "sub_instance",
    "AnimNode_PowerIK": "power_ik",
    "K2Node_Event": "event",
    "K2Node_CustomEvent": "custom_event",
    "K2Node_FunctionEntry": "function_entry",
    "K2Node_FunctionResult": "function_result",
    "K2Node_CallFunction": "call",
    "K2Node_VariableGet": "variable_get",
    "K2Node_VariableSet": "variable_set",
    "K2Node_IfThenElse": "branch",
    "K2Node_SwitchInteger": "switch",
    "K2Node_SwitchString": "switch",
    "K2Node_SwitchEnum": "switch",
    "K2Node_SwitchName": "switch",
    "K2Node_ExecutionSequence": "sequence",
    "K2Node_MultiGate": "sequence",
    "K2Node_MacroInstance": "macro",
    "K2Node_DynamicCast": "cast",
    "K2Node_ClassDynamicCast": "cast",
    "K2Node_MakeStruct": "make_struct",
    "K2Node_BreakStruct": "break_struct",
    "K2Node_CreateDelegate": "delegate_bind",
    "K2Node_AddDelegate": "delegate_bind",
    "K2Node_RemoveDelegate": "delegate_unbind",
    "K2Node_CallDelegate": "delegate_call",
    "K2Node_Literal": "literal",
    "K2Node_Knot": "reroute",
    "K2Node_Tunnel": "tunnel",
    "EdGraphNode_Comment": "comment",
}

_ANIM_GRAPH_KIND_RULES = (
    ("AnimGraph", "anim_graph"),
    ("UserConstructionScript", "construction_script"),
    ("MacroGraph", "macro"),
    ("collapsed", "collapsed_graph"),
    ("FunctionGraph", "function"),
    ("EdGraph", "event_graph"),
)


def anim_graph_kind(graph_name: str, graph_class: str) -> str:
    """Determine graph kind with animation-specific rules."""
    text = f"{graph_class}.{graph_name}".lower()
    for needle, kind in _ANIM_GRAPH_KIND_RULES:
        if needle.lower() in text:
            return kind
    return _graph_kind(graph_name, graph_class)


def anim_node_kind(node_class: str) -> tuple[str, str]:
    """Get the node kind and status for an animation node.

    Returns (kind, status) where status is 'recognized' or 'opaque'.

    Serialized graph nodes use AnimGraphNode_* class names; the underlying
    animation nodes use AnimNode_*. We normalize by stripping the "Graph"
    prefix for lookup.
    """
    if not node_class:
        return "custom", "opaque"

    # Try exact match first (handles both AnimNode_* and K2Node_* etc.)
    kind = _ANIM_NODE_KIND_MAP.get(node_class)
    if kind is not None:
        return kind, "recognized"

    # Normalize AnimGraphNode_* -> AnimNode_* for lookup
    lookup_name = node_class
    if node_class.startswith("AnimGraphNode_"):
        lookup_name = "AnimNode_" + node_class.removeprefix("AnimGraphNode_")
    kind = _ANIM_NODE_KIND_MAP.get(lookup_name)
    if kind is not None:
        return kind, "recognized"

    # Fall back to blueprint node kinds
    kind = _NODE_KIND_MAP.get(node_class)
    if kind is not None:
        return kind, "recognized"

    return "custom", "opaque"


def _pose_type(pin) -> str | None:
    """Detect Unreal pose link pin types.

    Returns:
        "local_space" for FPoseLink/PoseLink
        "component_space" for FComponentSpacePoseLink/ComponentSpacePoseLink
        None if not a pose pin
    """
    category = (getattr(pin, "pin_category", "") or "").lower()
    subcategory = (getattr(pin, "pin_subcategory", "") or "").lower()
    subcategory_obj = (getattr(pin, "pin_subcategory_object_name", "") or "").lower()

    # Explicit pose category
    if category == "pose":
        if "component" in subcategory or "componentspace" in subcategory:
            return "component_space"
        return "local_space"

    # Struct pins with pose link struct names
    if category == "struct":
        if subcategory in ("fposelink", "poselink"):
            return "local_space"
        if subcategory in ("fcomponentspaceposelink", "componentspaceposelink"):
            return "component_space"
        # Also check subcategory_object_name for the struct type
        if "fcomponentspaceposelink" in subcategory_obj or "componentspaceposelink" in subcategory_obj:
            return "component_space"
        if "fposelink" in subcategory_obj or "poselink" in subcategory_obj:
            return "local_space"

    return None


def emit_anim_node(node, graph_slug, ordinal_counts, table, reporting, mode):
    """Emit a single animation node with pose pin support."""
    node_class = getattr(node, "node_class", "") or getattr(node, "class_name", "") or ""
    kind, status = anim_node_kind(node_class)

    if kind == "comment":
        return None, {}

    raw_name = _node_name(node)
    name_slug = ascii_slug(raw_name)
    key = (kind, name_slug)
    ordinal = ordinal_counts.get(key, 0)
    ordinal_counts[key] = ordinal + 1
    nid = ab_node_id(graph_slug, kind, name_slug, ordinal)

    node_index: dict[str, dict] = {}
    data_pins: dict[str, dict] = {}
    control_ports: dict[str, dict] = {}
    pose_pins: dict[str, dict] = {}

    for pin in getattr(node, "pins", None) or []:
        pin_id = getattr(pin, "pin_guid", "") or ""
        direction = _direction_str(pin)
        is_exec = _is_exec(pin)
        pin_name = getattr(pin, "pin_name", "") or ""

        # Detect pose pins (animation-specific)
        pose = _pose_type(pin)
        is_pose = pose is not None

        if pose is not None:
            endpoint = pose_endpoint(pin_name, direction)
            pose_pins[endpoint] = {
                "name": pin_name,
                "direction": direction,
                "pose_type": pose,
            }
        elif is_exec:
            endpoint = exec_endpoint(pin_name)
        else:
            endpoint = data_endpoint(pin_name, direction)

        linked = _linked_guids(pin)
        if pin_id:
            node_index[pin_id] = {
                "node": nid,
                "graph": ab_graph_id(graph_slug),
                "endpoint": endpoint,
                "direction": direction,
                "is_exec": is_exec,
                "is_pose": is_pose,
                "orphaned": bool(getattr(pin, "orphaned", False)
                                 or getattr(pin, "orphaned_pin", False)),
                "not_connectable": bool(getattr(pin, "not_connectable", False)),
                "linked": linked,
            }

        connected = bool(linked)
        if is_pose:
            # Pose pins are always emitted
            pass
        elif is_exec:
            role = ascii_slug(pin_name).lower().replace("_", "-") or "port"
            control_ports[endpoint] = {"name": pin_name, "direction": direction, "role": role}
        elif _pin_keep(pin, connected):
            dpin: dict = {"name": pin_name, "direction": direction,
                          "type": type_ref_from_pin(table, pin)}
            if getattr(pin, "sub_pin_guids", None):
                dpin["path"] = [ascii_slug(pin_name)]
            if getattr(pin, "parent_pin_guid", ""):
                dpin["split_child"] = True
            data_pins[endpoint] = dpin

    result: dict = {"id": nid, "kind": kind}
    if raw_name != name_slug:
        result["label"] = raw_name
    if status != "recognized":
        result["status"] = status
        result["source_type"] = node_class
        # Emit diagnostic for unrecognized nodes
        reporting.diagnostic(
            "ABP_NODE_UNRECOGNIZED",
            f"graph:{ab_graph_id(graph_slug)}/nodes",
            "warning",
            "semantic_loss",
            occurrence={"class": node_class},
        )
    if data_pins:
        result["data_pins"] = data_pins
    if control_ports:
        result["control_ports"] = control_ports
    if pose_pins:
        result["pose_pins"] = pose_pins
    if mode == "debug":
        result["evidence"] = {"node_guid": getattr(node, "node_guid", "") or "",
                              "source_class": node_class}
    return result, node_index
