"""Graph/node/pin/port emission for Animation Blueprint semantic JSON.

Extends the Blueprint node emission with animation-specific node kinds:
- Pose nodes (input/output pose connections)
- State machine nodes
- Blend nodes
- Animation-specific nodes

Node emission itself is shared with ``blueprint.nodes._emit_node``; this
module only supplies the animation-specific classification, IDs and the
pose-pin classifier.
"""

from __future__ import annotations

from uasset_read.semantic.blueprint.nodes import (
    _NODE_KIND_MAP,
    _emit_node,
    _graph_kind,
)
from uasset_read.semantic.anim_blueprint.ids import (
    graph_id as ab_graph_id,
    node_id as ab_node_id,
    pose_endpoint,
)


# Animation-specific node kinds; Blueprint kinds are merged in below.
_ANIM_EXTRA_KIND_MAP = {
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
}

_ANIM_NODE_KIND_MAP = {**_NODE_KIND_MAP, **_ANIM_EXTRA_KIND_MAP}

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

    # Try exact match first (handles AnimNode_*, K2Node_* and EdGraphNode_*)
    kind = _ANIM_NODE_KIND_MAP.get(node_class)
    if kind is not None:
        return kind, "recognized"

    # Normalize AnimGraphNode_* -> AnimNode_* for lookup
    if node_class.startswith("AnimGraphNode_"):
        lookup_name = "AnimNode_" + node_class.removeprefix("AnimGraphNode_")
        kind = _ANIM_NODE_KIND_MAP.get(lookup_name)
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


def emit_anim_node(node, graph_slug, ordinal_counts, table, reporting):
    """Emit a single animation node with pose pin support."""
    return _emit_node(
        node,
        graph_slug,
        ordinal_counts,
        table,
        reporting,
        classify=anim_node_kind,
        diag_code="ABP_NODE_UNRECOGNIZED",
        gid_fn=ab_graph_id,
        nid_fn=ab_node_id,
        pose_fn=_pose_type,
        pose_endpoint_fn=pose_endpoint,
    )
