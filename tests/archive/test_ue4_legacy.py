"""UE4 Legacy 资产版本支持测试 — 验证 version -3 资产能正确解析。

测试覆盖:
- version -3 资产不被拒绝
- 解析结果标记为 legacy 模式
- CustomVersions 使用 Guids 格式读取
- 完整 header 解析流程
"""
from __future__ import annotations

import struct

import pytest

from uasset_read.constants import (
    PACKAGE_FILE_TAG,
    UE4_LEGACY_VERSIONS,
    UE5_LEGACY_VERSIONS,
    UE5_PACKAGE_SAVED_HASH,
    SUPPORTED_LEGACY_VERSIONS,
)


def _build_ue4_legacy_summary(
    legacy_file_version: int = -3,
    file_version_ue4: int = 522,
    file_version_licensee: int = 0,
    custom_version_guid: bytes | None = None,
    custom_version_value: int = 0,
) -> bytes:
    """构造最小 UE4 PackageFileSummary 二进制数据。

    UE4 LegacyFileVersion -3 的 header 布局:
    1. Tag (u32)
    2. LegacyFileVersion (i32) = -3
    3. LegacyUE3Version (i32)  [存在因为 -3 != -4]
    4. FileVersionUE4 (i32)
    5. FileVersionLicenseeUE4 (i32)
    6. CustomVersions (Guids 格式): count + [GUID(16) + i32 + FString]
    7. TotalHeaderSize (i32)
    ... 后续字段
    """
    data = bytearray()

    # 1. Tag
    data += struct.pack("<I", PACKAGE_FILE_TAG)
    # 2. LegacyFileVersion
    data += struct.pack("<i", legacy_file_version)
    # 3. LegacyUE3Version (存在因为 -3 != -4)
    if legacy_file_version != -4:
        data += struct.pack("<i", 0)
    # 4. FileVersionUE4
    data += struct.pack("<i", file_version_ue4)
    # 5. FileVersionLicenseeUE4
    data += struct.pack("<i", file_version_licensee)

    # 6. CustomVersions (Guids 格式: UE4 -3 到 -5)
    # Guids 格式: u32 count + 每条记录: GUID(16) + i32 version + FString friendly_name
    if custom_version_guid is not None:
        data += struct.pack("<I", 1)  # count = 1
        data += custom_version_guid  # 16 bytes GUID
        data += struct.pack("<i", custom_version_value)  # version
        # FString friendly_name: i32 length (含 null) + utf-8 chars + null
        name = b"TestVersion\x00"
        data += struct.pack("<i", len(name))  # length including null
        data += name
    else:
        data += struct.pack("<I", 0)  # count = 0

    # 7. TotalHeaderSize
    data += struct.pack("<i", len(data) + 4)  # 指向当前偏移之后

    # 后续字段填充（最小化）
    # PackageName (FString: i32 length + chars)
    data += struct.pack("<i", 0)  # 空字符串
    # PackageFlags
    data += struct.pack("<I", 0)
    # NameCount + NameOffset
    data += struct.pack("<ii", 0, 0)
    # ExportCount + ExportOffset
    data += struct.pack("<ii", 0, 0)
    # ImportCount + ImportOffset
    data += struct.pack("<ii", 0, 0)
    # DependsOffset
    data += struct.pack("<i", 0)
    # ThumbnailTableOffset
    data += struct.pack("<i", 0)
    # GenerationsCount
    data += struct.pack("<i", 0)
    # SavedByEngineVersion (2+2+2+4+ FString)
    data += struct.pack("<HHHi", 0, 0, 0, 0)
    data += struct.pack("<i", 0)  # empty FString
    # CompatibleWithEngineVersion
    data += struct.pack("<HHHi", 0, 0, 0, 0)
    data += struct.pack("<i", 0)  # empty FString
    # CompressionFlags + CompressedChunksCount
    data += struct.pack("<Ii", 0, 0)
    # PackageSource
    data += struct.pack("<I", 0)
    # AdditionalPackagesCount
    data += struct.pack("<i", 0)
    # NumTextureAllocations (legacy > -7)
    if legacy_file_version > -7:
        data += struct.pack("<i", 0)
    # AssetRegistryDataOffset
    data += struct.pack("<i", 0)
    # BulkDataStartOffset
    data += struct.pack("<q", 0)
    # WorldTileInfoDataOffset
    data += struct.pack("<i", 0)
    # ChunkIDsCount
    data += struct.pack("<i", 0)

    # 填充到足够大小，避免解析器读取越界
    # 预留 PreloadDependencies 等后续字段的空间
    data += b'\x00' * 256

    return bytes(data)


class TestUE4LegacyVersionAcceptance:
    """验证 UE4 legacy_file_version=-3 资产不被拒绝。"""

    def test_version_minus3_accepted(self):
        """legacy_file_version=-3 资产应被接受，不抛出 VersionError。"""
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        data = _build_ue4_legacy_summary(legacy_file_version=-3)
        archive = ByteArchive(data, name="test_legacy.uasset")

        summary = read_package_summary(archive)
        assert summary is not None
        assert summary.legacy_file_version == -3

    def test_version_minus4_accepted(self):
        """legacy_file_version=-4 资产应被接受。"""
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        data = _build_ue4_legacy_summary(legacy_file_version=-4)
        archive = ByteArchive(data, name="test_legacy.uasset")

        summary = read_package_summary(archive)
        assert summary is not None
        assert summary.legacy_file_version == -4

    def test_version_minus5_accepted(self):
        """legacy_file_version=-5 资产应被接受。"""
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        data = _build_ue4_legacy_summary(legacy_file_version=-5)
        archive = ByteArchive(data, name="test_legacy.uasset")

        summary = read_package_summary(archive)
        assert summary is not None
        assert summary.legacy_file_version == -5

    def test_version_minus1_still_rejected(self):
        """legacy_file_version=-1 应仍被拒绝（非标准 UE4 版本）。"""
        from uasset_read.exceptions import VersionError
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        data = _build_ue4_legacy_summary(legacy_file_version=-1)
        archive = ByteArchive(data, name="test_legacy.uasset")

        with pytest.raises(VersionError):
            read_package_summary(archive)


class TestUE4LegacyIsLegacyFlag:
    """验证 UE4 legacy 资产的 is_legacy 标记。"""

    def test_version_minus3_is_legacy(self):
        """legacy_file_version=-3 的 summary 应标记 is_legacy=True。"""
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        data = _build_ue4_legacy_summary(legacy_file_version=-3)
        archive = ByteArchive(data, name="test_legacy.uasset")

        summary = read_package_summary(archive)
        assert summary.is_legacy is True

    def test_version_minus9_is_not_legacy(self):
        """legacy_file_version=-9 (UE5) 的 summary 不应标记 is_legacy。"""
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        # 使用 UE5 格式（需要 FileVersionUE5 字段）
        data = bytearray()
        data += struct.pack("<I", PACKAGE_FILE_TAG)
        data += struct.pack("<i", -9)  # LegacyFileVersion
        data += struct.pack("<i", 0)  # LegacyUE3Version
        data += struct.pack("<i", 0)  # FileVersionUE4
        data += struct.pack("<i", 1016)  # FileVersionUE5 (>= PACKAGE_SAVED_HASH)
        data += struct.pack("<i", 0)  # FileVersionLicensee
        data += b"\x00" * 20  # SavedHash
        data += struct.pack("<i", len(data) + 4)  # TotalHeaderSize
        data += struct.pack("<I", 0)  # CustomVersionsCount
        # PackageName
        data += struct.pack("<i", 0)
        # PackageFlags
        data += struct.pack("<I", 0)
        # NameCount + NameOffset
        data += struct.pack("<ii", 0, 0)
        # ExportCount + ExportOffset
        data += struct.pack("<ii", 0, 0)
        # ImportCount + ImportOffset
        data += struct.pack("<ii", 0, 0)
        # DependsOffset
        data += struct.pack("<i", 0)
        # ThumbnailTableOffset
        data += struct.pack("<i", 0)
        # GenerationsCount
        data += struct.pack("<i", 0)
        # SavedByEngineVersion
        data += struct.pack("<HHHi", 0, 0, 0, 0)
        data += struct.pack("<i", 0)
        # CompatibleWithEngineVersion
        data += struct.pack("<HHHi", 0, 0, 0, 0)
        data += struct.pack("<i", 0)
        # CompressionFlags + CompressedChunksCount
        data += struct.pack("<Ii", 0, 0)
        # PackageSource
        data += struct.pack("<I", 0)
        # AdditionalPackagesCount
        data += struct.pack("<i", 0)
        # NumTextureAllocations (legacy > -7: -9 is not > -7, so skip)
        # AssetRegistryDataOffset
        data += struct.pack("<i", 0)
        # BulkDataStartOffset
        data += struct.pack("<q", 0)
        # WorldTileInfoDataOffset
        data += struct.pack("<i", 0)
        # ChunkIDsCount
        data += struct.pack("<i", 0)
        # 填充到足够大小
        data += b'\x00' * 256

        archive = ByteArchive(bytes(data), name="test_ue5.uasset")

        summary = read_package_summary(archive)
        assert summary.is_legacy is False


class TestUE4LegacyCustomVersions:
    """验证 UE4 legacy 资产的 CustomVersions 使用 Guids 格式读取。"""

    def test_custom_version_guids_format(self):
        """-3 资产的 custom versions 应使用 Guids 格式（含 FriendlyName）。"""
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        # 构造一个已知的 GUID
        guid = bytes([
            0xCF, 0xFC, 0x74, 0x3F,
            0x43, 0xB0, 0x44, 0x80,
            0x93, 0x91, 0x14, 0xDF,
            0x17, 0x1D, 0x20, 0x73,
        ])

        data = _build_ue4_legacy_summary(
            legacy_file_version=-3,
            custom_version_guid=guid,
            custom_version_value=42,
        )
        archive = ByteArchive(data, name="test_legacy.uasset")

        summary = read_package_summary(archive)
        assert len(summary.custom_versions) == 1
        cv = summary.custom_versions[0]
        assert cv.guid == guid.hex()
        assert cv.version == 42

    def test_empty_custom_versions(self):
        """-3 资产无 custom versions 时应正常处理。"""
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        data = _build_ue4_legacy_summary(legacy_file_version=-3)
        archive = ByteArchive(data, name="test_legacy.uasset")

        summary = read_package_summary(archive)
        assert summary.custom_versions == []


class TestUE4LegacyConstants:
    """验证 UE4 legacy 版本常量定义正确。"""

    def test_ue4_legacy_versions_set(self):
        """UE4_LEGACY_VERSIONS 应包含 -3, -4, -5。"""
        assert UE4_LEGACY_VERSIONS == frozenset({-3, -4, -5})

    def test_supported_legacy_versions_union(self):
        """SUPPORTED_LEGACY_VERSIONS 应是 UE5 和 UE4 的并集。"""
        assert SUPPORTED_LEGACY_VERSIONS == UE5_LEGACY_VERSIONS | UE4_LEGACY_VERSIONS
        assert -3 in SUPPORTED_LEGACY_VERSIONS
        assert -9 in SUPPORTED_LEGACY_VERSIONS

    def test_version_minus3_in_supported(self):
        """-3 应在 SUPPORTED_LEGACY_VERSIONS 中。"""
        assert -3 in SUPPORTED_LEGACY_VERSIONS


# ===========================================================================
# 版本兼容性测试 — 验证 UE4 legacy 资产的 VersionError 提示信息
# ===========================================================================

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
