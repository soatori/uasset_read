"""UAnimCurveCompressionCodec Asset type handler (opaque partial metadata).

Pure UPROPERTY serialization, no custom Serialize().
Defines the animation curve compression codec.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_anim_curve_compression_codec = make_opaque_stub("AnimCurveCompressionCodec")
