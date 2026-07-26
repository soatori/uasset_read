"""TextureCube Asset metadata extractor (partial metadata).

Note: This module does not attempt to parse the UE standard UTextureCube::Serialize layout.
Only extracts raw byte samples for diagnostics.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_texture_cube = make_opaque_stub("TextureCube")
