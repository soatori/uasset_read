"""UMediaTexture type handler (opaque partial metadata).

UMediaTexture renders video frames as a texture.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_media_texture = make_opaque_stub("MediaTexture")
