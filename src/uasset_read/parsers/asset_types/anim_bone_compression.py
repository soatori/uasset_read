"""UAnimBoneCompressionSettings 资产类型处理器（opaque partial metadata）。

纯 UPROPERTY 序列化，无自定义 Serialize()。
AnimSequence 使用此类型决定骨骼压缩策略。
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_anim_bone_compression_settings = make_opaque_stub("AnimBoneCompressionSettings")
