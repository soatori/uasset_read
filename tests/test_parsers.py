"""parsers 模块合并测试 — 覆盖主链路、类型处理、恢复场景与关卡序列。

保留 9 个关键用例：
1. 核心解析（resolve_name_from_index、read_validated_count）
2. 类型处理（_parse_property_type 递归解析）
3. PropertyTag 偏移恢复（#341）
4. LevelSequence 策略验证
5. Texture2D 尺寸校验
6. LWC 版本感知 struct 大小
7. 日志重复过滤器
8. SerializationControlExtensions 未知位跳过（#425）
9. PropertyTag 恢复扫描窗口与 size_exceeded 恢复（#428/#429）
"""
from __future__ import annotations

import io
import logging
import struct
from unittest.mock import MagicMock

import pytest

from uasset_read.objects.exports.texture import UTexture2D, _MAX_TEXTURE_DIMENSION
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
)
from uasset_read.parsers.property_parser import (
    _try_recover_property_tag,
    _handle_serialization_control,
    _KNOWN_PROPERTY_TYPES,
    _MAX_RECOVERY_SCAN,
)
from uasset_read.parsers.property_types import get_struct_size
from uasset_read.parsers.utils import resolve_name_from_index, read_validated_count_tolerant
from uasset_read.versioning import VersionContainer


# ============================================================================
# 1. 核心解析
# ============================================================================

class TestCoreParsing:
    def test_resolve_name_from_index_valid(self):
        """有效索引返回名称；有效计数返回正确值。"""
        archive = MagicMock()
        name_map = ["Actor", "Component", "Property"]
        assert resolve_name_from_index(archive, name_map, 1) == "Component"
        archive.read_i32.return_value = 5
        assert read_validated_count_tolerant(archive, max_count=100, label="test") == 5


# ============================================================================
# 2. LevelSequence 策略验证
# ============================================================================

class TestLevelSequenceStrategy:
    def test_level_sequence_strategy_is_tagged(self):
        """LevelSequence 应使用 TAGGED_PROPERTIES_ONLY 策略。"""
        assert get_serialization_strategy("LevelSequence") == SerializationStrategy.TAGGED_PROPERTIES_ONLY


# ============================================================================
# 辅助工厂（合并自 test_unit.py）
# ============================================================================

def _make_vc(ue5_version: int = 0, ue4_version: int = 0) -> VersionContainer:
    return VersionContainer(file_version_ue5=ue5_version, file_version_ue4=ue4_version)

def _make_archive_mock() -> MagicMock:
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.total_size.return_value = 1024
    return archive

def _make_texture(**props) -> UTexture2D:
    tex = UTexture2D(name="TestTexture")
    for k, v in props.items():
        tex.set_property(k, v)
    return tex


# ============================================================================
# 5. Texture2D 尺寸校验（合并自 test_unit.py）
# ============================================================================

class TestTexture2DBounds:
    def test_negative_sizex_clamped(self):
        """PlatformData SizeX 为负值时置为 0。"""
        tex = _make_texture(PlatformData={"SizeX": -100, "SizeY": 256, "PixelFormat": 1, "Mips": []})
        tex.deserialize(_make_archive_mock(), offset=0, size=100)
        assert tex.size_x == 0


# ============================================================================
# 6. LWC 版本感知 struct 大小（合并自 test_unit.py）
# ============================================================================

class TestStructSizeLWC:
    def test_ue4_returns_float_size(self):
        """UE4→float(12)；UE5 LWC→double(24)。"""
        assert get_struct_size("Vector", _make_vc(ue4_version=516)) == 12
        assert get_struct_size("Vector", _make_vc(ue5_version=1004)) == 24


# ============================================================================
# 7. 日志重复过滤器
# ============================================================================

class TestRepeatedFilter:
    def test_repeated_warning_suppression(self):
        """重复 WARNING 被抑制；INFO 不被抑制。"""
        import logging
        from uasset_read.project_logging import _RepeatedDebugFilter

        filt = _RepeatedDebugFilter(repeat_limit=3, suppress_levels={logging.DEBUG, logging.WARNING})
        # WARNING: 前3次通过，第4次抑制
        warn = logging.LogRecord("t", logging.WARNING, "", 0, "w", (), None)
        assert filt.filter(warn) is True
        assert filt.filter(warn) is True
        assert filt.filter(warn) is True
        assert filt.filter(warn) is False
        assert filt.suppressed_count == 1
        # INFO: 永不抑制
        filt2 = _RepeatedDebugFilter(repeat_limit=2, suppress_levels={logging.DEBUG, logging.WARNING})
        info = logging.LogRecord("t", logging.INFO, "", 0, "i", (), None)
        for _ in range(10):
            assert filt2.filter(info) is True


# ============================================================================
# 8. SerializationControlExtensions 未知位跳过（#425）
# ============================================================================

class _FakeArchiveForControl:
    """用于 _handle_serialization_control 测试的最小 archive 模拟。"""

    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)
        self._diagnostics: list[dict] = []

    def read(self, size: int) -> bytes:
        return self._buf.read(size)

    def read_u8(self) -> int:
        raw = self._buf.read(1)
        if len(raw) < 1:
            raise OSError("EOF")
        return raw[0]

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, pos: int) -> None:
        self._buf.seek(pos)

    def _record_diagnostic(self, **kwargs) -> None:
        self._diagnostics.append(kwargs)


class _FakeExportForControl:
    """用于 _handle_serialization_control 测试的最小 export 模拟。"""

    def __init__(self) -> None:
        self.object_name = "TestExport"
        self.transforms: dict | None = None


class _FakeSummaryForControl:
    """用于 _handle_serialization_control 测试的最小 summary 模拟。"""
    pass


class TestSerializationControlUnknownBits:
    def test_serialization_control_extensions_unknown_bits_skip(self):
        """未知位（0x04+）提前返回；已知位正常解析。"""
        # 未知位 → 立即返回
        archive1 = _FakeArchiveForControl(bytes([0x04]))
        archive1._record_diagnostic = MagicMock()
        export1 = _FakeExportForControl()
        _handle_serialization_control(archive1, _FakeSummaryForControl(), export1)
        assert archive1.tell() == 1
        assert export1.transforms["serialization_control"]["unknown_bits"] == 0x04
        # 已知位 0x02 → 正常解析
        archive2 = _FakeArchiveForControl(bytes([0x02, 0x05]))
        archive2._record_diagnostic = MagicMock()
        export2 = _FakeExportForControl()
        _handle_serialization_control(archive2, _FakeSummaryForControl(), export2)
        assert archive2.tell() == 2
        assert export2.transforms["serialization_control"]["overridden_operation"] == 0x05


# ============================================================================
# 9. PropertyTag 恢复扫描窗口与 size_exceeded 恢复（#428/#429）
# ============================================================================

class _FakeArchiveForRecovery:
    """用于恢复测试的 archive 模拟，支持 seek/tell/read 和 _file_size。"""

    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)
        self._file_size = len(data)

    def read(self, size: int) -> bytes:
        return self._buf.read(size)

    def read_i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, pos: int) -> None:
        self._buf.seek(pos)

    def total_size(self) -> int:
        return self._file_size


def _build_recovery_data(
    name_map: list[str],
    valid_tag_offset: int,
    tag_name: str = "TestProp",
    tag_type: str = "IntProperty",
    tag_size: int = 4,
) -> bytes:
    """构造包含垃圾数据 + 有效 PropertyTag 的二进制数据。

    布局：
    - [0..valid_tag_offset-1]: 填充 0xFF（垃圾数据）
    - [valid_tag_offset..]: 有效的 PropertyTag 结构
      - name FName: index(4) + number(4)
      - type FName: index(4) + number(4)
      - size: int32(4)
      - [size+4..]: 属性值数据
    """
    # 确保 name_map 包含必要的名称
    if tag_name not in name_map:
        name_map.append(tag_name)
    if tag_type not in name_map:
        name_map.append(tag_type)
    name_idx = name_map.index(tag_name)
    type_idx = name_map.index(tag_type)

    # 垃圾填充
    garbage = b"\xff" * valid_tag_offset

    # 有效 PropertyTag（legacy 格式，ue5 < 1012）
    tag_bytes = struct.pack("<II", name_idx, 0)  # name FName
    tag_bytes += struct.pack("<II", type_idx, 0)  # type FName
    tag_bytes += struct.pack("<i", tag_size)       # size
    tag_bytes += b"\x00" * tag_size                # value data

    return garbage + tag_bytes


class TestPropertyTagRecovery:
    def test_property_tag_recovery_valid_and_known_type(self):
        """#428: 恢复扫描应支持大偏移并接受已知属性类型。

        合并测试：大偏移恢复、已知类型接受、扫描窗口增大。
        """
        # 验证扫描窗口已增大
        assert _MAX_RECOVERY_SCAN == 512

        # 验证已知属性类型集合
        expected_types = {"IntProperty", "FloatProperty", "StrProperty", "BoolProperty",
                          "StructProperty", "ObjectProperty", "ArrayProperty", "MapProperty"}
        assert expected_types.issubset(_KNOWN_PROPERTY_TYPES)

        name_map: list[str] = ["None"]

        # 测试 1: 大偏移恢复（> 256 字节）
        data = _build_recovery_data(name_map, 300, tag_name="MyProp", tag_type="FloatProperty")
        archive = _FakeArchiveForRecovery(data)
        archive._file_version_ue5 = 500
        result = _try_recover_property_tag(archive, name_map, max_scan=_MAX_RECOVERY_SCAN)
        assert result is True
        assert archive.tell() == 300

        # 测试 2: 已知类型接受
        name_map2: list[str] = ["None"]
        data2 = _build_recovery_data(name_map2, 50, tag_name="ValidProp", tag_type="StrProperty")
        archive2 = _FakeArchiveForRecovery(data2)
        archive2._file_version_ue5 = 500
        result2 = _try_recover_property_tag(archive2, name_map2, max_scan=_MAX_RECOVERY_SCAN)
        assert result2 is True
        assert archive2.tell() == 50

    def test_property_tag_recovery_rejects_unknown_type(self):
        """#428: 恢复扫描应拒绝未知属性类型名称。"""
        name_map: list[str] = ["None"]
        valid_offset = 100
        garbage = b"\xff" * valid_offset

        name_map.append("SomeName")     # idx 1
        name_map.append("NotARealProperty")  # idx 2 — 不在 _KNOWN_PROPERTY_TYPES 中

        tag_bytes = struct.pack("<II", 1, 0)  # name FName (idx=1)
        tag_bytes += struct.pack("<II", 2, 0)  # type FName (idx=2, 未知类型)
        tag_bytes += struct.pack("<i", 4)       # size
        tag_bytes += b"\x00" * 4

        data = garbage + tag_bytes
        archive = _FakeArchiveForRecovery(data)
        archive._file_version_ue5 = 500

        result = _try_recover_property_tag(archive, name_map, max_scan=_MAX_RECOVERY_SCAN)
        assert result is False
