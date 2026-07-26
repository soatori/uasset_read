"""UAnimBoneCompressionSettings Asset type handler (opaque partial metadata).

Pure UPROPERTY serialization, no custom Serialize().
AnimSequence uses this type to determine bone compression strategy.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_anim_bone_compression_settings = make_opaque_stub("AnimBoneCompressionSettings")
