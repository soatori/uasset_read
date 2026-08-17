"""UAnimLayerInterface type handler (opaque partial metadata).

UAnimLayerInterface defines animation layer interfaces for blend state machines.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_anim_layer_interface = make_opaque_stub("AnimLayerInterface")
