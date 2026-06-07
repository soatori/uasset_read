"""版本兼容性测试 — 验证 UE4 legacy 资产的 VersionError 提示信息。"""
from __future__ import annotations

import struct

import pytest

from uasset_read.constants import (
    PACKAGE_FILE_TAG,
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
    """验证 UE4 legacy_file_version 触发的 VersionError 包含 UE4 提示。"""

    def test_legacy_version_minus3_raises_version_error_with_ue4_hint(self):
        """legacy_file_version=-3（UE4 ParticleSystem 等资产）应提示 UE4 不支持。"""
        from uasset_read.exceptions import VersionError
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        archive = ByteArchive(
            "P_Fire.uasset",
            _minimal_package_with_legacy_version(-3),
        )

        with pytest.raises(VersionError, match=r"Legacy file version -3 indicates UE4 asset") as exc_info:
            read_package_summary(archive)

        # 验证错误消息包含完整提示
        msg = str(exc_info.value)
        assert "UE4" in msg
        assert "UE5" in msg
        assert "-6 to -9" in msg

    @pytest.mark.parametrize("legacy_version", [-1, -2, -3, -4, -5])
    def test_all_ue4_legacy_versions_produce_ue4_hint(self, legacy_version: int):
        """所有 UE4 legacy version（>-6 且不在支持集合中）应统一提示 UE4 不支持。"""
        from uasset_read.exceptions import VersionError
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        archive = ByteArchive(
            "test.uasset",
            _minimal_package_with_legacy_version(legacy_version),
        )

        with pytest.raises(VersionError, match=rf"Legacy file version {legacy_version} indicates UE4 asset"):
            read_package_summary(archive)

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
            "test.uasset",
            _minimal_package_summary_bytes(legacy_version, file_version_ue5=file_version_ue5),
        )
        # UE5 支持的 legacy version 不应抛出 UE4 相关的 VersionError
        # （可能因后续字段不完整抛出其他错误，但不应是 UE4 提示）
        try:
            read_package_summary(archive)
        except VersionError as e:
            assert "UE4 asset" not in str(e), (
                f"UE5 legacy version {legacy_version} 不应触发 UE4 错误提示: {e}"
            )
