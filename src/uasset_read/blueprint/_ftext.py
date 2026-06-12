"""FText 读取工具 — 从 variable_extractor.py 抽取。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary


def _text_or_string(value: Any) -> str:
    if hasattr(value, "source_string"):
        return str(value.source_string)
    return str(value or "")


def read_ftext(archive, summary=None) -> str:
    """读取 FText 结构（用于 FBPVariableDescription.Category 等字段）。

    UE FText 序列化格式 (Text.cpp:845-964):
      - flags: i32 (4 bytes)
      - history_type: i8 (1 byte) — 版本门控 (VER_UE4_FTEXT_HISTORY = 428)
      - body: 根据 history_type 不同而不同

    简化实现：提取 source_string 作为结果。

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary（用于版本检查，可选）

    Returns:
        FText 的 source_string 内容
    """
    from uasset_read.constants import VER_UE4_FTEXT_HISTORY

    # 1. 读取 flags (未使用)
    _flags = archive.read_i32()

    # 2. 检查版本，读取 history_type
    ue4_version = summary.file_version_ue4 if summary and hasattr(summary, 'file_version_ue4') else 500
    if ue4_version >= VER_UE4_FTEXT_HISTORY:
        history_type = archive.read_i8()
    else:
        # 旧版本无 history_type，直接读取 Base 格式
        history_type = 0

    # 3. 根据 history_type 读取数据
    if history_type == 0:  # Base
        # namespace + key + source_string
        archive.read_fstring()  # namespace
        archive.read_fstring()  # key
        source_string = archive.read_fstring()
        return source_string

    elif history_type == 1:  # NamedFormat
        # 包含格式化参数，简化处理
        archive.read_fstring()  # namespace
        archive.read_fstring()  # key
        # 读取参数字典并丢弃
        _skip_ftext_args(archive)
        return ""

    elif history_type == 2:  # OrderedFormat
        archive.read_fstring()  # namespace
        archive.read_fstring()  # key
        source_string = archive.read_fstring()
        _skip_ftext_args(archive)
        return source_string

    elif history_type == 3:  # ArgumentFormat
        archive.read_fstring()  # namespace
        archive.read_fstring()  # key
        source_string = archive.read_fstring()
        _skip_ftext_args(archive)
        return source_string

    elif history_type in (4, 5, 6, 7, 8, 9, 10):
        # AsNumber, AsPercent, AsCurrency, DateString, TimeString, DateTimeString, Transform
        archive.read_fstring()  # namespace
        archive.read_fstring()  # key
        source_string = archive.read_fstring()
        archive.read_fstring()  # 额外字段
        return source_string

    else:
        # 未知的 history_type，无法安全跳过
        return ""


def _skip_ftext_args(archive) -> None:
    """跳过 FText 参数字典（仅消耗字节）。"""
    from uasset_read.parsers.utils import read_validated_count
    count = read_validated_count(archive, 10_000, "FText args")
    for _ in range(count):
        archive.read_fstring()  # key
        archive.read_fstring()  # value
