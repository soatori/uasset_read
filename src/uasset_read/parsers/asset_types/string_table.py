"""UStringTable 资产类型处理器（opaque partial metadata）。

UStringTable 仅使用标准 UPROPERTY 序列化（TableNamespace、StringTable TMap），
无自定义 Serialize()。Handler 提供类型识别。
"""
from __future__ import annotations

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_string_table = make_opaque_stub("StringTable")
