"""parsers 模块测试 — 核心解析、类型处理、PropertyTag 恢复。"""
from __future__ import annotations

import io
import struct
from unittest.mock import MagicMock

import pytest

from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
)
from uasset_read.parsers.property_parser import (
    _try_recover_property_tag,
    _KNOWN_PROPERTY_TYPES,
    _MAX_RECOVERY_SCAN,
)
from uasset_read.parsers.property_types import get_struct_size
from uasset_read.parsers.utils import resolve_name_from_index, read_validated_count_tolerant
from uasset_read.versioning import VersionContainer


def _make_vc(ue5_version: int = 0, ue4_version: int = 0) -> VersionContainer:
    return VersionContainer(file_version_ue5=ue5_version, file_version_ue4=ue4_version)


class TestCoreParsing:
    def test_resolve_name_from_index_valid(self):
        """有效索引返回名称；有效计数返回正确值。"""
        archive = MagicMock()
        name_map = ["Actor", "Component", "Property"]
        assert resolve_name_from_index(archive, name_map, 1) == "Component"
        archive.read_i32.return_value = 5
        assert read_validated_count_tolerant(archive, max_count=100, label="test") == 5


class TestLevelSequenceStrategy:
    def test_level_sequence_strategy_is_tagged(self):
        """LevelSequence 应使用 TAGGED_PROPERTIES_ONLY 策略。"""
        assert get_serialization_strategy("LevelSequence") == SerializationStrategy.TAGGED_PROPERTIES_ONLY


class TestStructSizeLWC:
    def test_ue4_returns_float_size(self):
        """UE4→float(12)；UE5 LWC→double(24)。"""
        assert get_struct_size("Vector", _make_vc(ue4_version=516)) == 12
        assert get_struct_size("Vector", _make_vc(ue5_version=1004)) == 24


class _FakeArchiveForRecovery:
    """用于恢复测试的 archive 模拟。"""

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
    """构造包含垃圾数据 + 有效 PropertyTag 的二进制数据。"""
    if tag_name not in name_map:
        name_map.append(tag_name)
    if tag_type not in name_map:
        name_map.append(tag_type)
    name_idx = name_map.index(tag_name)
    type_idx = name_map.index(tag_type)

    garbage = b"\xff" * valid_tag_offset
    tag_bytes = struct.pack("<II", name_idx, 0)
    tag_bytes += struct.pack("<II", type_idx, 0)
    tag_bytes += struct.pack("<i", tag_size)
    tag_bytes += b"\x00" * tag_size

    return garbage + tag_bytes


class TestPropertyTagRecovery:
    def test_property_tag_recovery_valid_and_known_type(self):
        """恢复扫描应支持大偏移并接受已知属性类型。"""
        assert _MAX_RECOVERY_SCAN == 512

        expected_types = {"IntProperty", "FloatProperty", "StrProperty", "BoolProperty",
                          "StructProperty", "ObjectProperty", "ArrayProperty", "MapProperty"}
        assert expected_types.issubset(_KNOWN_PROPERTY_TYPES)

        name_map: list[str] = ["None"]
        data = _build_recovery_data(name_map, 300, tag_name="MyProp", tag_type="FloatProperty")
        archive = _FakeArchiveForRecovery(data)
        archive._file_version_ue5 = 500
        result = _try_recover_property_tag(archive, name_map, max_scan=_MAX_RECOVERY_SCAN)
        assert result is True
        assert archive.tell() == 300

    def test_property_tag_recovery_rejects_unknown_type(self):
        """恢复扫描应拒绝未知属性类型名称。"""
        name_map: list[str] = ["None"]
        valid_offset = 100
        garbage = b"\xff" * valid_offset

        name_map.append("SomeName")
        name_map.append("NotARealProperty")

        tag_bytes = struct.pack("<II", 1, 0)
        tag_bytes += struct.pack("<II", 2, 0)
        tag_bytes += struct.pack("<i", 4)
        tag_bytes += b"\x00" * 4

        data = garbage + tag_bytes
        archive = _FakeArchiveForRecovery(data)
        archive._file_version_ue5 = 500

        result = _try_recover_property_tag(archive, name_map, max_scan=_MAX_RECOVERY_SCAN)
        assert result is False
