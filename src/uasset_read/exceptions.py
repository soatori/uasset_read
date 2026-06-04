"""
uasset_read异常类定义

包含所有异常类，用于错误处理和优雅降级。
从uasset_read.py提取（per D-13）。
"""

from dataclasses import dataclass, field
from typing import Optional, Dict


# ============================================================================
# 自定义异常（优雅降级）
# ============================================================================

class UAssetError(Exception):
    """uasset解析错误基类"""
    pass


class VersionError(UAssetError):
    """版本不支持错误"""
    pass


@dataclass
class ErrorContext:
    """
    错误上下文信息。

    记录错误发生时的解析状态，帮助定位问题。
    """

    offset: int           # 文件偏移位置
    phase: str            # 解析阶段：header/name_table/import_map/export_map/properties/blueprint
    operation: str        # 操作类型：read_i32/read_name/seek 等
    context_name: str = ""  # 相关对象名或属性名
    # 导出表解析阶段信息
    export_index: Optional[int] = None    # 当前导出索引（0-based）
    expected_offset: Optional[int] = None  # 期望偏移
    actual_offset: Optional[int] = None    # 实际偏移
    field_name: str = ""                  # 字段名（如 "TemplateIndex"）
    version_info: Dict[str, int] = field(default_factory=dict)  # 版本检查失败信息


class ParseError(UAssetError):
    """解析错误（可携带部分结果和上下文）"""

    def __init__(self, message: str, partial_result: Optional[Dict] = None, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.partial_result = partial_result
        self.context = context