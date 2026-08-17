"""UMaterialParameterCollection Asset type handler (opaque partial metadata).

UMaterialParameterCollection contains scalar and vector parameters
that can be referenced by any material.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_material_parameter_collection = make_opaque_stub("MaterialParameterCollection")
