"""Package Summary 主读取入口。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.constants import (
    PACKAGE_FILE_TAG, PACKAGE_FILE_TAG_SWAPPED,
    UE4_LEGACY_VERSIONS, UE5_LEGACY_VERSIONS,
    MIN_UASSET_SIZE,
)
from uasset_read.exceptions import VersionError, ParseError
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from .models import PackageFileSummary
from .ue4_reader import read_ue4_package_summary
from .ue5_reader import read_ue5_package_summary


def _is_ue4_legacy(legacy_file_version: int) -> bool:
    """判断是否为 UE4 资产。"""
    if legacy_file_version in UE4_LEGACY_VERSIONS:
        return True
    if legacy_file_version in UE5_LEGACY_VERSIONS:
        return False
    return legacy_file_version > -6


def read_package_summary(archive: "FArchive") -> PackageFileSummary:
    """读取 PackageFileSummary 文件头（UE5/UE4 兼容）。"""
    # 截断文件检测
    file_size = archive.total_size()
    if file_size < MIN_UASSET_SIZE:
        archive._diagnostics.append(OffsetRangeDiagnostic(
            kind="truncated_file",
            module="package_summary",
            field="file_size",
            file_size=file_size,
            source="read_package_summary",
            error=(
                f"文件大小 {file_size} 字节，小于最小合法大小 {MIN_UASSET_SIZE} 字节，"
                f"文件可能已截断或损坏"
            ),
        ))
        raise ParseError(
            f"文件过小（{file_size} 字节），无法解析为 .uasset 文件。"
            f"最小合法大小为 {MIN_UASSET_SIZE} 字节，文件可能已截断或损坏"
        )

    archive.seek(0)

    # 魔数和版本号
    tag = archive.read_u32()
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
        tag = PACKAGE_FILE_TAG
    elif tag != PACKAGE_FILE_TAG:
        raise VersionError(f"Invalid package tag: {hex(tag)}")

    legacy_file_version = archive.read_i32()

    # 确定引擎家族并分发
    if legacy_file_version == -6:
        saved_pos = archive.tell()
        archive.read_i32()
        file_version_ue4_peek = archive.read_i32()
        archive.seek(saved_pos)
        is_ue4 = file_version_ue4_peek > 0
    else:
        is_ue4 = _is_ue4_legacy(legacy_file_version)

    if is_ue4:
        return read_ue4_package_summary(archive, tag, legacy_file_version)
    else:
        return read_ue5_package_summary(archive, tag, legacy_file_version)


def validate_export_data_range(
    archive: "FArchive",
    summary: PackageFileSummary,
) -> None:
    """验证导出数据偏移是否超出文件范围。"""
    from uasset_read.serializers.object_resources import ObjectExport

    file_size = archive.total_size()
    if file_size <= 0 or summary.export_count <= 0:
        return

    export_table_min_entry_size = 72
    export_table_end = summary.export_offset + summary.export_count * export_table_min_entry_size
    if export_table_end > file_size:
        archive._diagnostics.append(OffsetRangeDiagnostic(
            kind="truncated_file",
            module="package_summary",
            field="export_table",
            current_pos=summary.export_offset,
            target_offset=export_table_end,
            file_size=file_size,
            source="validate_export_data_range",
            error=(
                f"导出表区域 [0x{summary.export_offset:X}, 0x{export_table_end:X}] "
                f"超出文件大小 0x{file_size:X}，文件可能在导出表区域被截断"
            ),
        ))
