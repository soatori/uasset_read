"""USparseVolumeTexture type handler (opaque partial metadata).

USparseVolumeTexture is a sparse 3D texture for virtual texturing.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_sparse_volume_texture = make_opaque_stub("SparseVolumeTexture")
