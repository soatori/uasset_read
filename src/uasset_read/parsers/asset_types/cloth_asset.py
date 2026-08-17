"""UClothAsset type handler (opaque partial metadata).

UClothAsset contains cloth simulation data (UE5).
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_cloth_asset = make_opaque_stub("ClothAsset")
