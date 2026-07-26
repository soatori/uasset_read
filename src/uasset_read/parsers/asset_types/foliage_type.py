"""UFoliageType Asset type handler (opaque partial metadata).

UFoliageType::Serialize() only calls Super::Serialize(), data serialized via UPROPERTY.
The current generic tagged property parser cannot fully parse its payload,
so we provide type identification as an opaque stub.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_foliage_type = make_opaque_stub("FoliageType")
