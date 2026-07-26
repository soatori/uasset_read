"""Texture2D Asset metadata extractor (partial metadata).

Note: This module does not attempt to parse the UE standard UTexture2D::Serialize layout
(that layout depends on version, CustomVersion, and FTexturePlatformData structure).
Only extracts raw byte samples for diagnostics.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_texture2d = make_opaque_stub("Texture2D")
