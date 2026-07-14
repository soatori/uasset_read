"""版本兼容性测试 — 验证 UE4 legacy 资产的 VersionError 提示信息。

版本 -3, -4, -5 现在作为 UE4 Legacy 资产被接受（Task #397）。
版本 -1, -2 仍被拒绝（非标准/过旧版本）。
"""
from __future__ import annotations

import struct

import pytest

from uasset_read.constants import (
    PACKAGE_FILE_TAG,
    UE4_LEGACY_VERSIONS,
    UE5_LEGACY_VERSIONS,
    UE5_PACKAGE_SAVED_HASH,
)


def _minimal_package_with_legacy_version(legacy_file_version: int) -> bytes:
    """构造最小合法二进制头部，用于触发 VersionError。"""
    data = bytearray()
    # Tag + LegacyFileVersion + LegacyUE3Version + FileVersionUE4
    data += struct.pack("<Iiii", PACKAGE_FILE_TAG, legacy_file_version, 0, 0)
    # 补充足够字段让 FArchive 不会在 header 阶段越界
    data += struct.pack("<i", 0)  # file_version_licensee
    data += struct.pack("<I", 0)  # custom_versions_count
    data += struct.pack("<i", 0)  # total_header_size
    data += struct.pack("<i", 0)  # package_name (空字符串)
    data += struct.pack("<I", 0)  # package_flags
    # 填充到 MIN_UASSET_SIZE (64) 以满足截断文件检测
    data += b'\x00' * (64 - len(data))
    return bytes(data)


def _minimal_package_summary_bytes(
    legacy_file_version: int,
    *,
    file_version_ue5: int | None = None,
) -> bytes:
    """构造完整最小 UE5 PackageFileSummary，避免跨 test module 导入。"""
    data = bytearray()
    data += struct.pack("<Iiii", PACKAGE_FILE_TAG, legacy_file_version, 0, 0)
    if legacy_file_version <= -8:
        ue5 = file_version_ue5 if file_version_ue5 is not None else 1016
        data += struct.pack("<i", ue5)
    data += struct.pack("<i", 0)  # file_version_licensee
    if file_version_ue5 is not None and file_version_ue5 >= UE5_PACKAGE_SAVED_HASH:
        data += b"\x00" * 20
        data += struct.pack("<i", 0)
    data += struct.pack("<I", 0)  # custom_versions_count
    ue5_val = file_version_ue5 if file_version_ue5 is not None else 0
    if ue5_val < UE5_PACKAGE_SAVED_HASH:
        data += struct.pack("<i", 0)
    data += struct.pack("<i", 0)  # package_name
    data += struct.pack("<I", 0)  # package_flags
    data += struct.pack("<iiiiiiiiiiiii", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    data += struct.pack("<i", 0)  # depends_offset
    data += struct.pack("<i", 0)  # thumbnail_table_offset
    data += struct.pack("<i", 0)  # generations_count
    data += struct.pack("<HHHIi", 0, 0, 0, 0, 0)
    data += struct.pack("<HHHIi", 0, 0, 0, 0, 0)
    data += struct.pack("<IiIi", 0, 0, 0, 0)
    data += struct.pack("<i", 0)
    data += struct.pack("<q", 0)
    data += struct.pack("<i", 0)
    data += struct.pack("<i", 0)
    data += struct.pack("<ii", 0, 0)
    data += struct.pack("<i", 0)
    data += struct.pack("<q", 0)
    data += struct.pack("<i", 0)
    return bytes(data)


class TestUE4LegacyVersionError:
    """验证 UE4 legacy_file_version 触发的 VersionError 提示信息。

    版本 -3, -4, -5 现在作为 UE4 Legacy 资产被接受（Task #397）。
    仅 -1, -2 仍被拒绝（非标准/过旧版本）。
    """

    @pytest.mark.parametrize("legacy_version", [-1, -2])
    def test_unsupported_legacy_versions_still_rejected(self, legacy_version: int):
        """legacy_file_version=-1, -2 应仍被拒绝（非标准/过旧版本）。"""
        from uasset_read.exceptions import VersionError
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        archive = ByteArchive(
            _minimal_package_with_legacy_version(legacy_version),
            name="test.uasset",
        )

        with pytest.raises(VersionError, match=rf"Unsupported legacy_file_version {legacy_version}"):
            read_package_summary(archive)

    @pytest.mark.parametrize("legacy_version", sorted(UE4_LEGACY_VERSIONS))
    def test_ue4_legacy_versions_are_accepted(self, legacy_version: int):
        """UE4 legacy version -3, -4, -5 应被接受，不抛出 VersionError。"""
        from uasset_read.exceptions import VersionError, ParseError
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        archive = ByteArchive(
            _minimal_package_with_legacy_version(legacy_version),
            name="test.uasset",
        )

        # UE4 legacy version 不应抛出 VersionError
        # （可能因后续字段不完整抛出 ParseError，但不应是版本错误）
        try:
            summary = read_package_summary(archive)
            assert summary is not None
            assert summary.is_legacy is True
        except VersionError:
            pytest.fail(f"UE4 legacy version {legacy_version} 不应抛出 VersionError")
        except ParseError:
            pass  # 最小数据不完整导致的 ParseError 是预期的

    @pytest.mark.parametrize("legacy_version", sorted(UE5_LEGACY_VERSIONS))
    def test_ue5_legacy_versions_do_not_raise_ue4_error(self, legacy_version: int):
        """UE5 支持的 legacy version 不应触发 UE4 错误提示。"""
        from uasset_read.exceptions import VersionError
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        # 与 test_package_summary_fields.py 中已有测试保持一致的 file_version_ue5 映射
        if legacy_version == -7:
            file_version_ue5 = None  # legacy -7 无 FileVersionUE5 字段
        elif legacy_version == -8:
            file_version_ue5 = 1004  # < UE5_PACKAGE_SAVED_HASH，走后续读取路径
        else:
            file_version_ue5 = 1016  # >= UE5_PACKAGE_SAVED_HASH

        archive = ByteArchive(
            _minimal_package_summary_bytes(legacy_version, file_version_ue5=file_version_ue5),
            name="test.uasset",
        )
        # UE5 支持的 legacy version 不应抛出 UE4 相关的 VersionError
        # （可能因后续字段不完整抛出其他错误，但不应是 UE4 提示）
        try:
            read_package_summary(archive)
        except VersionError as e:
            assert "UE4 asset" not in str(e), (
                f"UE5 legacy version {legacy_version} 不应触发 UE4 错误提示: {e}"
            )
