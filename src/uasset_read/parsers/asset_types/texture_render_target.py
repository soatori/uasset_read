"""TextureRenderTarget Asset type handlers (opaque partial metadata).

Handles UTextureRenderTarget2D, UTextureRenderTargetCube.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_texture_render_target = make_opaque_stub("TextureRenderTarget")
