"""ULevel type handler (opaque partial metadata).

ULevel contains actor and BSP data for a streaming level.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_level = make_opaque_stub("Level")
