"""UPrimaryDataAsset type handler (opaque partial metadata).

UPrimaryDataAsset extends DataAsset with asset manager integration.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_primary_data_asset = make_opaque_stub("PrimaryDataAsset")
