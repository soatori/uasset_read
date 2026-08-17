"""ULandscapeGrassType type handler (opaque partial metadata).

ULandscapeGrassType defines grass mesh spawning configuration.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_landscape_grass_type = make_opaque_stub("LandscapeGrassType")
