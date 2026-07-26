"""StaticMesh Asset metadata extractor (partial metadata).

Note: This module does not attempt to parse the UE standard UStaticMesh::Serialize layout
(that layout depends on version, CustomVersion, and FStaticMeshRenderData structure).
Only extracts raw byte samples for diagnostics.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_static_mesh = make_opaque_stub("StaticMesh")
