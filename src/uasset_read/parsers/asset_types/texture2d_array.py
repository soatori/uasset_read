"""UTexture2DArray type handler (opaque partial metadata).

UTexture2DArray is an array of Texture2D slices.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_texture2d_array = make_opaque_stub("Texture2DArray")
