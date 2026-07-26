"""SkeletalMesh Asset metadata extractor (partial metadata).

Note: This module does not attempt to parse the UE standard USkeletalMesh::Serialize layout
(that layout depends on version, CustomVersion, and FSkeletalMeshRenderData structure).
Only extracts raw byte samples for diagnostics.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_skeletal_mesh = make_opaque_stub("SkeletalMesh")
