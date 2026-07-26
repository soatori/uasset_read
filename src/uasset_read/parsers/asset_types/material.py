"""Material Asset metadata extractor (partial metadata).

Note: This module does not attempt to parse the UE standard UMaterial::Serialize layout
(that layout depends on version, CustomVersion, and FMaterialResource structure).
It only extracts raw byte samples for diagnostics.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_material = make_opaque_stub("Material")
