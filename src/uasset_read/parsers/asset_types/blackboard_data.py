"""UBlackboardData type handler (opaque partial metadata).

UBlackboardData defines AI blackboard key schemas.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_blackboard_data = make_opaque_stub("BlackboardData")
