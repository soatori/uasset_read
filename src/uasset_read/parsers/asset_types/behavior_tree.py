"""UBehaviorTree type handler (opaque partial metadata).

UBehaviorTree contains AI behavior tree graph data.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_behavior_tree = make_opaque_stub("BehaviorTree")
