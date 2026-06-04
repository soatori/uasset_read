"""src/uasset_read/models/diagnostics.py — 偏移范围诊断数据模型。

用于记录解析过程中遇到的偏移/范围异常情况，
包括序列偏移越界、脚本偏移溢出、CodeOffset 异常等。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class OffsetRangeDiagnostic:
    """偏移范围诊断记录 — 捕获解析过程中的偏移异常。"""

    kind: str = "offset_range_diagnostic"
    asset_path: str = ""
    asset_type: str = ""
    module: str = ""  # linker|property|graph|pin|kismet|pak|iostore
    object_name: str = ""
    export_index: Optional[int] = None
    import_index: Optional[int] = None
    field: str = ""  # serial_offset|script_serial_offset|ValueEndOffset|CodeOffset|LinkedTo
    current_pos: int = 0
    target_offset: int = 0
    read_size: int = 0
    file_size: int = 0
    range_start: Optional[int] = None
    range_end: Optional[int] = None
    source: str = ""
    error: str = ""
    fallback_used: bool = False
    fallback_result: str = ""  # failed|partial|success

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 兼容字典。None 值字段自动省略。"""
        d: Dict[str, Any] = {
            "kind": self.kind,
        }
        # 字符串字段：非空时输出
        for str_field in (
            "asset_path", "asset_type", "module", "object_name",
            "field", "source", "error", "fallback_result",
        ):
            val = getattr(self, str_field)
            if val:
                d[str_field] = val
        # 整数字段：始终输出（含 0）
        for int_field in ("current_pos", "target_offset", "read_size", "file_size"):
            d[int_field] = getattr(self, int_field)
        # 可选整数字段：非 None 时输出
        for opt_field in ("export_index", "import_index", "range_start", "range_end"):
            val = getattr(self, opt_field)
            if val is not None:
                d[opt_field] = val
        # 布尔字段：True 时输出
        if self.fallback_used:
            d["fallback_used"] = True
        return d
