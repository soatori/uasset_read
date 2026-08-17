"""ALandscape type handler (opaque partial metadata).

ALandscape is the terrain actor with heightmap and layer data.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_landscape = make_opaque_stub("Landscape")
