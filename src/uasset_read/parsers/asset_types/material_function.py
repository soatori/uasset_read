"""UMaterialFunction Asset type handler (opaque partial metadata).

UMaterialFunction is a reusable collection of material expressions.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_material_function = make_opaque_stub("MaterialFunction")
