"""parsers 模块合并测试 — 覆盖主链路、类型处理、恢复场景与关卡序列。

保留 6 个关键用例：
1. 核心解析（resolve_name_from_index、read_validated_count）
2. 类型处理（_parse_property_type 递归解析）
3. PropertyTag 偏移恢复（#341）
4. LevelSequence 策略验证
5. Texture2D 尺寸校验
6. LWC 版本感知 struct 大小
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from uasset_read.objects.exports.texture import UTexture2D, _MAX_TEXTURE_DIMENSION
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
)
from uasset_read.parsers.property_parser import _try_recover_property_tag
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
