"""UAnimCurveCompressionCodec 资产类型处理器（opaque partial metadata）。

纯 UPROPERTY 序列化，无自定义 Serialize()。
定义动画曲线的压缩编解码器。
"""
from __future__ import annotations

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_anim_curve_compression_codec = make_opaque_stub("AnimCurveCompressionCodec")
