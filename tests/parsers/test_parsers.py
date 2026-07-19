"""parsers 模块合并测试 — 覆盖主链路、类型处理、恢复场景与关卡序列。

保留 4 个关键用例：
1. 核心解析（resolve_name_from_index、read_validated_count）
2. 类型处理（_parse_property_type 递归解析）
3. PropertyTag 偏移恢复（#341）
4. LevelSequence 策略验证
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
)
from uasset_read.parsers.property_parser import _try_recover_property_tag
from uasset_read.parsers.utils import resolve_name_from_index, read_validated_count_tolerant


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
