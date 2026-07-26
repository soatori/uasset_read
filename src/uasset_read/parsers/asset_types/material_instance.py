"""MaterialInstanceConstant Asset metadata extractor (partial metadata).

Note: This module does not attempt to parse the UE standard UMaterialInstanceConstant::Serialize layout
(that layout depends on version, CustomVersion, and FMaterialParameterInfo structure).
It only extracts raw byte samples for diagnostics.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_material_instance = make_opaque_stub("MaterialInstanceConstant")
