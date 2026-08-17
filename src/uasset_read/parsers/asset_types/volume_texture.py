"""UVolumeTexture type handler (opaque partial metadata).

UVolumeTexture is a 3D texture (volume).
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_volume_texture = make_opaque_stub("VolumeTexture")
