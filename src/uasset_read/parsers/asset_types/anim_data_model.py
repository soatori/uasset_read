"""AnimDataModel 资产元数据提取器（partial metadata）。

UAnimDataModel 使用标准 UPROPERTY 序列化（无自定义 Serialize()），
当前仅提取原始字节样本供诊断使用。
"""
from __future__ import annotations

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_anim_data_model = make_opaque_stub("AnimationDataModel")
