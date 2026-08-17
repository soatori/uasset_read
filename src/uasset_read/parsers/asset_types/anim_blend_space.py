"""BlendSpace Asset type handlers (opaque partial metadata).

Handles UBlendSpace, UBlendSpace1D, UAimOffsetBlendSpace, UAimOffsetBlendSpace1D.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_anim_blend_space = make_opaque_stub("AnimBlendSpace")
