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


class DecompressionError(UAssetError):
    """解压缩失败（zlib/Oodle/LZ4 等）"""
    pass


class LinkerError(UAssetError):
    """Linker 阶段错误（import/export 解析失败）"""
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
    """解析错误（可携带部分结果、上下文和丰富的诊断信息）。

    Attributes:
        partial_result: 部分解析结果（容错场景）
        context: 旧版 ErrorContext（向后兼容）
        reader_name: 读取器名称（如 FArchive、ByteArchive）
        position: 当前读取位置
        length: 文件总长度
        export_name: 当前导出名称（如有）
    """

    def __init__(self, message: str, partial_result: Optional[Dict] = None, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.partial_result = partial_result
        self.context = context
        # 新增上下文信息
        self.reader_name: str = ""
        self.position: int = 0
        self.length: int = 0
        self.export_name: str = ""

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.reader_name:
            parts.append(f"Reader: {self.reader_name}")
        if self.length > 0:
            pct = (self.position / self.length * 100) if self.length > 0 else 0
            parts.append(f"Position: {self.position} / {self.length} ({pct:.1f}% done)")
        if self.export_name:
            parts.append(f"Export: {self.export_name}")
        return "\n".join(parts)