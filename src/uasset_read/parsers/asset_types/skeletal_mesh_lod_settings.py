"""USkeletalMeshLODSettings Asset type handler (opaque partial metadata).

USkeletalMeshLODSettings's Serialize() only calls Super::Serialize(),
data serialized via UPROPERTY. However, the current generic tagged property parser
cannot fully parse its payload, so it is provided as an opaque stub for type identification.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_skeletal_mesh_lod_settings = make_opaque_stub("SkeletalMeshLODSettings")
