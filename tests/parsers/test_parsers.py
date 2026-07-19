"""parsers 模块合并测试 — 覆盖主链路、类型处理、恢复场景与关卡序列。

保留 6 个关键用例：
1. 核心解析（resolve_name_from_index、read_validated_count）
2. 类型处理（_parse_property_type 递归解析）
3. PropertyTag 偏移恢复（#341）
4. ArrayProperty tag.size < 4 处理（#345）
5. 自定义属性分派（handle_custom_property）
6. LevelSequence 策略验证
"""
from __future__ import annotations

import struct
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.models.properties import PropertyTag
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
)
from uasset_read.parsers.custom_properties import handle_custom_property
from uasset_read.parsers.property_parser import _try_recover_property_tag, _MAX_RECOVERY_SCAN
from uasset_read.parsers.property_types import parse_array_property
from uasset_read.parsers.usmap import _parse_property_type
from uasset_read.parsers.usmap import _BytesReader, MAX_RECURSION_DEPTH
from uasset_read.parsers.utils import resolve_name_from_index, read_validated_count_tolerant


# ============================================================================
# 辅助工厂
# ============================================================================

def _make_mock_archive_for_recovery(data: bytes, pos: int = 0, *, file_version_ue5: int = 1012):
    """创建 mock FArchive 用于 PropertyTag 恢复测试。"""
    archive = MagicMock()
    archive._data = data
    archive._pos = pos
    archive._file_size = len(data)
    archive._file_version_ue5 = file_version_ue5

    def tell():
        return archive._pos
    def seek(p):
        archive._pos = p
    def read(n):
        start = archive._pos
        archive._pos += n
        return data[start:start + n]

    archive.tell = tell
    archive.seek = seek
    archive.read = read
    return archive


# ============================================================================
# 用例 1: 核心解析
# ============================================================================

class TestCoreParsing:
    """resolve_name_from_index 与 read_validated_count_tolerant。"""

    def test_resolve_name_from_index_valid(self):
        """有效索引应返回正确的名称。"""
        name_map = ["foo", "bar", "baz"]
        assert resolve_name_from_index(None, name_map, 0) == "foo"
        assert resolve_name_from_index(None, name_map, 2) == "baz"

    def test_resolve_name_from_index_out_of_range(self):
        """越界索引应返回 fallback。"""
        assert resolve_name_from_index(None, ["foo"], 5) == "param_5"

    def test_read_validated_count_valid(self):
        """有效数量应正常返回。"""
        class FakeArchive:
            def __init__(self, d):
                self._data = d
                self._pos = 0
            def tell(self):
                return self._pos
            def read_i32(self):
                val = struct.unpack_from("<i", self._data, self._pos)[0]
                self._pos += 4
                return val
        archive = FakeArchive(struct.pack("<i", 10))
        assert read_validated_count_tolerant(archive, 100, "test") == 10

    def test_read_validated_count_negative_returns_zero(self):
        """负数应返回 0。"""
        class FakeArchive:
            def __init__(self, d):
                self._data = d
                self._pos = 0
            def tell(self):
                return self._pos
            def read_i32(self):
                val = struct.unpack_from("<i", self._data, self._pos)[0]
                self._pos += 4
                return val
        archive = FakeArchive(struct.pack("<i", -5))
        assert read_validated_count_tolerant(archive, 100, "test") == 0


# ============================================================================
# 用例 2: 类型处理（_parse_property_type 递归解析）
# ============================================================================

class TestParsePropertyType:
    """_parse_property_type — 递归类型解析。"""

    @staticmethod
    def _make_reader(type_id: int, extra: bytes = b"") -> _BytesReader:
        return _BytesReader(struct.pack("<B", type_id) + extra)

    def test_simple_int(self):
        """IntProperty 应正确解析。"""
        reader = self._make_reader(2)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "IntProperty"
        assert prop.inner_type is None

    def test_array_property(self):
        """ArrayProperty 应递归解析 inner_type。"""
        reader = self._make_reader(8, struct.pack("<B", 2))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "ArrayProperty"
        assert prop.inner_type is not None
        assert prop.inner_type.type_name == "IntProperty"

    def test_map_property(self):
        """MapProperty 应递归解析 key 和 value 类型。"""
        reader = self._make_reader(24, struct.pack("<BB", 2, 3))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "MapProperty"
        assert prop.inner_type.type_name == "IntProperty"
        assert prop.value_type.type_name == "FloatProperty"

    def test_depth_limit_exceeded(self):
        """超过递归深度上限应抛出 ParseError。"""
        reader = self._make_reader(2)
        with pytest.raises(ParseError, match="递归深度超过上限"):
            _parse_property_type(reader, [], depth=MAX_RECURSION_DEPTH + 1)


# ============================================================================
# 用例 3: PropertyTag 偏移恢复（#341）
# ============================================================================

class TestPropertyTagRecovery:
    """#341: PropertyTag 损坏时的恢复机制。"""

    def test_recovery_finds_valid_tag_signature(self):
        """恢复函数应能找到有效的 PropertyTag。"""
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 10)
        data = b'\x00\x00\x00' + fname + type_fname + size + b'\xff' * 30
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=0)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_returns_false_when_no_valid_tag(self):
        """无有效 tag 时应返回 False。"""
        data = b'\xff' * 100
        archive = _make_mock_archive_for_recovery(data, pos=0)
        result = _try_recover_property_tag(archive, ["None"], max_scan=32)
        assert result is False


# ============================================================================
# 用例 4: ArrayProperty tag.size < 4 处理（#345）
# ============================================================================

class TestArrayPropertySmallSize:
    """#345: tag.size < 4 时不应读取 count。"""

    def test_small_tag_size_skips_count_read(self):
        """tag.size < 4 应返回空数组，不读取 count。"""
        class TrackingArchive:
            def __init__(self):
                self.pos = 0
                self.read_count = 0
            def tell(self):
                return self.pos
            def read_i32(self):
                self.read_count += 1
                self.pos += 4
                return 0
            def read_fstring(self):
                return ""
            def read_byte(self):
                return 0

        for size in (0, 1, 3):
            a = TrackingArchive()
            tag = PropertyTag(name="A", type="ArrayProperty", size=size)
            result = parse_array_property(tag, a, [], [])
            assert result == [], f"size={size}: 应返回空数组"
            assert a.read_count == 0, f"size={size}: 不应调用 read_i32"


# ============================================================================
# 用例 5: 自定义属性分派
# ============================================================================

class TestCustomPropertyDispatch:
    """handle_custom_property — 按优先级分派到正确的处理器。"""

    def test_no_handler_returns_unhandled_fallback(self):
        """无处理器时应返回 unhandled fallback 结果。"""
        tag = MagicMock()
        tag.type = "UnknownCustomType"
        tag.size = 4
        archive = MagicMock()
        archive.read.return_value = b"\x00\x01\x02\x03"
        result = handle_custom_property(type_id=0xFF, tag=tag, archive=archive)
        assert result is not None
        assert result["kind"] == "custom_property_unhandled"
        assert result["type_id"] == 0xFF

    def test_game_specific_handler_takes_priority(self):
        """游戏特定处理器应优先于通用处理器。"""
        tag = MagicMock()
        tag.type = "GbxDefPtrProperty"
        tag.size = 0
        archive = MagicMock()
        archive.read.return_value = b""
        archive.read_name.return_value = "TestName"
        archive.read_i32.return_value = 42
        result = handle_custom_property(type_id=0xFD, tag=tag, archive=archive, game="Borderlands4")
        assert result is not None
        assert result.get("kind") == "GbxDefPtrProperty"


# ============================================================================
# 用例 6: LevelSequence 策略验证
# ============================================================================

class TestLevelSequenceStrategy:
    """LevelSequence 应使用 TAGGED_PROPERTIES_ONLY 策略。"""

    def test_level_sequence_strategy_is_tagged(self):
        """LevelSequence 策略必须是 TAGGED_PROPERTIES_ONLY。"""
        strategy = get_serialization_strategy("LevelSequence")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_level_sequence_not_opaque(self):
        """LevelSequence 不应走 OPAQUE_CLASS_PAYLOAD 策略。"""
        strategy = get_serialization_strategy("LevelSequence")
        assert strategy != SerializationStrategy.OPAQUE_CLASS_PAYLOAD
