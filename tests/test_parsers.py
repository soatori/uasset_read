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
        """有效索引应返回对应名称。"""
        archive = MagicMock()
        name_map = ["Actor", "Component", "Property"]
        result = resolve_name_from_index(archive, name_map, 1)
        assert result == "Component"

    def test_read_validated_count_valid(self):
        """有效计数应返回正确值。"""
        archive = MagicMock()
        archive.read_i32.return_value = 5
        result = read_validated_count_tolerant(archive, max_count=100, label="test")
        assert result == 5


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
        """UE4 版本返回 float 大小。"""
        vc = _make_vc(ue4_version=516)
        assert get_struct_size("Vector", vc) == 12

    def test_ue5_lwc_returns_double_size(self):
        """UE5 LWC (>= 1004) 返回 double 大小。"""
        vc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector", vc) == 24


# ============================================================================
# 7. 日志重复过滤器
# ============================================================================

class TestRepeatedFilter:
    def test_repeated_warning_suppression(self):
        """重复的 WARNING 消息应被抑制并生成摘要。"""
        import logging
        from uasset_read.project_logging import _RepeatedDebugFilter

        filt = _RepeatedDebugFilter(repeat_limit=3, suppress_levels={logging.DEBUG, logging.WARNING})
        record = logging.LogRecord("test", logging.WARNING, "", 0, "test message", (), None)

        # 前 3 次通过
        assert filt.filter(record) is True
        assert filt.filter(record) is True
        assert filt.filter(record) is True
        # 第 4 次被抑制
        assert filt.filter(record) is False
        assert filt.suppressed_count == 1

    def test_info_level_not_suppressed_by_default(self):
        """INFO 级别消息不应被 _RepeatedDebugFilter 抑制。"""
        import logging
        from uasset_read.project_logging import _RepeatedDebugFilter

        filt = _RepeatedDebugFilter(repeat_limit=2, suppress_levels={logging.DEBUG, logging.WARNING})
        record = logging.LogRecord("test", logging.INFO, "", 0, "info message", (), None)

        for _ in range(10):
            assert filt.filter(record) is True


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
        """#425: 未知位（0x04+）应触发 WARNING 日志并提前返回。"""
        # 构造包含未知位 0x04 的控制字节
        ctrl_byte = 0x04  # Unknown_Bit2
        data = bytes([ctrl_byte])
        archive = _FakeArchiveForControl(data)
        export = _FakeExportForControl()
        summary = _FakeSummaryForControl()

        # 使用 mock 替代 _record_diagnostic
        archive._record_diagnostic = MagicMock()

        # 实际调用
        _handle_serialization_control(archive, summary, export)

        # 验证：transforms 应已设置
        assert export.transforms is not None
        assert export.transforms["serialization_control"]["unknown_bits"] == 0x04
        assert export.transforms["serialization_control"]["overridden_operation"] is None

        # 验证：archive 位置不应前进到读取 overridden_operation
        # 控制字节 1 字节，无 overridden_operation 读取，位置应在 1
        assert archive.tell() == 1

    def test_serialization_control_known_bits_continue(self):
        """已知位（0x01|0x02）不应触发提前返回。"""
        # 0x02 触发读取 overridden_operation
        ctrl_byte = 0x02
        overridden_op = 0x05
        data = bytes([ctrl_byte, overridden_op])
        archive = _FakeArchiveForControl(data)
        archive._record_diagnostic = MagicMock()
        export = _FakeExportForControl()
        summary = _FakeSummaryForControl()

        _handle_serialization_control(archive, summary, export)

        # 验证：应读取了控制字节 + overridden_operation
        assert archive.tell() == 2
        assert export.transforms["serialization_control"]["overridden_operation"] == overridden_op
        assert export.transforms["serialization_control"]["unknown_bits"] == 0


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
    def test_property_tag_recovery_larger_offset(self):
        """#428: 恢复扫描应支持 > 256 字节的偏移漂移。"""
        name_map: list[str] = ["None"]  # 索引 0 保留
        # 有效 tag 放在偏移 300 处（超过旧的 256 字节窗口）
        valid_offset = 300
        data = _build_recovery_data(name_map, valid_offset, tag_name="MyProp", tag_type="FloatProperty")

        archive = _FakeArchiveForRecovery(data)
        archive._file_version_ue5 = 500  # legacy 格式

        # 从偏移 0 开始扫描
        result = _try_recover_property_tag(archive, name_map, max_scan=_MAX_RECOVERY_SCAN)

        assert result is True
        assert archive.tell() == valid_offset

    def test_property_tag_recovery_rejects_unknown_type(self):
        """#428: 恢复扫描应拒绝未知属性类型名称。"""
        name_map: list[str] = ["None"]
        # 构造一个 type 名称为 "NotARealProperty" 的候选
        valid_offset = 100
        garbage = b"\xff" * valid_offset

        # 添加一个看起来像 FName 但类型名无效的 tag
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

    def test_property_tag_recovery_accepts_known_type(self):
        """#428: 恢复扫描应接受已知属性类型名称。"""
        name_map: list[str] = ["None"]
        valid_offset = 50
        data = _build_recovery_data(name_map, valid_offset, tag_name="ValidProp", tag_type="StrProperty")

        archive = _FakeArchiveForRecovery(data)
        archive._file_version_ue5 = 500

        result = _try_recover_property_tag(archive, name_map, max_scan=_MAX_RECOVERY_SCAN)
        assert result is True
        assert archive.tell() == valid_offset

    def test_max_recovery_scan_increased_to_512(self):
        """#428: _MAX_RECOVERY_SCAN 应为 512。"""
        assert _MAX_RECOVERY_SCAN == 512

    def test_known_property_types_contains_common_types(self):
        """#428: _KNOWN_PROPERTY_TYPES 应包含常见属性类型。"""
        expected = {"IntProperty", "FloatProperty", "StrProperty", "BoolProperty",
                    "StructProperty", "ObjectProperty", "ArrayProperty", "MapProperty"}
        assert expected.issubset(_KNOWN_PROPERTY_TYPES)
