"""Blueprint 元数据键集中定义测试 — 验证常量和过滤函数一致性。"""
from __future__ import annotations

import pytest


class TestBlueprintMetadataKeysCentralized:
    """验证 _BLUEPRINT_METADATA_KEYS 在 constants.py 中集中定义。"""

    def test_constant_exists_in_constants(self):
        """BLUEPRINT_METADATA_KEYS 应在 constants.py 中定义。"""
        from uasset_read.constants import BLUEPRINT_METADATA_KEYS
        assert isinstance(BLUEPRINT_METADATA_KEYS, frozenset)
        assert len(BLUEPRINT_METADATA_KEYS) > 0

    def test_cpp_constructor_uses_centralized_constant(self):
        """cpp_constructor_ir_builder.py 应使用 constants.py 中的常量。"""
        from uasset_read.constants import BLUEPRINT_METADATA_KEYS
        from uasset_read.cpp_gen.cpp_constructor_ir_builder import (
            _BLUEPRINT_METADATA_KEYS as ctor_keys,
            _is_blueprint_metadata,
        )
        # 应引用同一集合
        assert ctor_keys is BLUEPRINT_METADATA_KEYS or ctor_keys == BLUEPRINT_METADATA_KEYS
        # 过滤函数应正确工作
        assert _is_blueprint_metadata("BlueprintSystemVersion") is True
        assert _is_blueprint_metadata("MyVariable") is False

    def test_ir_builder_uses_centralized_constant(self):
        """ir_builder.py 应使用 constants.py 中的常量。"""
        from uasset_read.constants import BLUEPRINT_METADATA_KEYS
        from uasset_read.ir_builder import _BLUEPRINT_METADATA_KEYS as ir_keys
        assert ir_keys is BLUEPRINT_METADATA_KEYS or ir_keys == BLUEPRINT_METADATA_KEYS

    def test_required_keys_present(self):
        """元数据键集合应包含所有必需的 UE 内部字段。"""
        from uasset_read.constants import BLUEPRINT_METADATA_KEYS
        required = {
            "BlueprintSystemVersion",
            "GeneratedClass",
            "SimpleConstructionScript",
            "bCanEverTick",
            "bCanEverRender",
        }
        missing = required - BLUEPRINT_METADATA_KEYS
        assert len(missing) == 0, f"缺少必需元数据键: {missing}"
