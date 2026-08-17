"""UDataAsset type handler (opaque partial metadata).

UDataAsset is a base class for custom data containers.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_data_asset = make_opaque_stub("DataAsset")
