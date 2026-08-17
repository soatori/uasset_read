"""UWorld type handler (opaque partial metadata).

UWorld is the top-level container for a game level.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_world = make_opaque_stub("World")
