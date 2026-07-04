"""SoundWave 资产元数据提取器（partial metadata）。

注意：本模块不尝试解析 UE 标准 USoundWave::Serialize 布局。
仅提取原始字节样本供诊断使用。
"""
from __future__ import annotations

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_sound_wave = make_opaque_stub("SoundWave")
