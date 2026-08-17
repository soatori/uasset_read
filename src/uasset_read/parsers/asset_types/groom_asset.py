"""UGroomAsset type handler (opaque partial metadata).

UGroomAsset contains strand-based hair/fur data (UE5).
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_groom_asset = make_opaque_stub("GroomAsset")
