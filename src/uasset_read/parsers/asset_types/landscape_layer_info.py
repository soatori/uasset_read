"""ULandscapeLayerInfoObject type handler (opaque partial metadata).

ULandscapeLayerInfoObject defines landscape layer blend configuration.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_landscape_layer_info = make_opaque_stub("LandscapeLayerInfoObject")
