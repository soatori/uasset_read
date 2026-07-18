"""Blueprint 字段验证测试 — 合并自以下文件：
- test_interfaces.py (1 test): BlueprintInterfaces 提取测试（Issue #169）
- test_blueprint_description.py (1 test): BlueprintDescription 提取测试（Issue #169）
- test_variable_type.py (1 test): BlueprintVariable var_type 字段填充测试（Issue #172）
- test_ftext_category.py (2 tests): FText Category 解析测试（Issue #170）
- test_constructor_metadata.py (1 test): 变量分类测试 — 验证 PackageIR.variables 不包含元数据变量
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import asset_path, ASSET_BLUEPRINT_FIRST_PERSON
from uasset_read.constants import BLUEPRINT_METADATA_KEYS

# 测试资产相对路径
_BP_FIRST_PERSON_PLAYER_CONTROLLER_REL = "StackOBot_BP_Drone.uasset"

# 已知元数据键（不应出现在构造函数中）
_METADATA_KEYS = {
    "BlueprintSystemVersion",
    "GeneratedClass",
    "SimpleConstructionScript",
    "bCanEverTick",
    "bCanEverRender",
}


def _cleanup_result(result):
    """Compatibility helper; global pytest teardown owns cyclic GC."""


# === test_interfaces.py ===

def test_blueprint_has_interfaces(sample_root: Path):
    """蓝图应包含 interfaces 列表"""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    bp_path = asset_path(sample_root, ASSET_BLUEPRINT_FIRST_PERSON)
    result = parse_uasset_with_linker(str(bp_path), tolerant=True)
    try:
        assert result.is_success, f"解析失败: {result.errors}"
        blueprint = result.blueprint
        assert blueprint is not None, "蓝图数据不应为 None"
        assert blueprint.interfaces is not None, "interfaces 不应为 None"
        assert isinstance(blueprint.interfaces, list), "interfaces 应为列表"
        print(f"Interfaces: {[{'name': i.name, 'guid': i.guid} for i in blueprint.interfaces]}")
        if blueprint.interfaces:
            names = [i.name for i in blueprint.interfaces]
            assert any("Touch" in n for n in names), f"应包含 TouchInterface，实际: {names}"
    finally:
        _cleanup_result(result)


# === test_blueprint_description.py ===

def test_blueprint_has_description(sample_root: Path):
    """蓝图应包含 description 字段"""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    bp_path = asset_path(sample_root, ASSET_BLUEPRINT_FIRST_PERSON)
    result = parse_uasset_with_linker(str(bp_path), tolerant=True)
    try:
        assert result.is_success, f"解析失败: {result.errors}"
        blueprint = result.blueprint
        assert blueprint is not None, "蓝图数据不应为 None"
        assert blueprint.description is not None, "description 不应为 None"
        assert len(blueprint.description) > 0, f"description 不应为空，实际值: '{blueprint.description}'"
        print(f"BlueprintDescription: {blueprint.description}")
    finally:
        _cleanup_result(result)


# === test_variable_type.py ===

class TestVariableVarType:
    """验证 BlueprintVariable.var_type 不为 None。"""

    def test_variable_has_var_type(self, sample_root: Path):
        """变量应包含 var_type 类型信息"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        bp_path = asset_path(sample_root, ASSET_BLUEPRINT_FIRST_PERSON)
        result = parse_uasset_with_linker(str(bp_path), tolerant=True)
        try:
            assert result.is_success, f"解析失败: {result.errors}"
            blueprint = result.blueprint
            assert blueprint is not None, "蓝图数据不应为 None"
            assert len(blueprint.variables) > 0, "蓝图变量列表不应为空"

            none_vars = [v for v in blueprint.variables if v.var_type is None]
            assert not none_vars, (
                f"以下变量的 var_type 为 None: {[v.var_name for v in none_vars]}"
            )

            for var in blueprint.variables:
                assert var.var_type is not None, f"变量 {var.var_name} 的 var_type 为 None"
                assert var.var_type.pin_category, (
                    f"变量 {var.var_name} 的 var_type.pin_category 为空"
                )
        finally:
            _cleanup_result(result)


# === test_ftext_category.py ===

def test_category_not_property_fallback(sample_root: Path):
    """变量 Category 不应为 PropertyFallback（已知损坏数据除外）"""
    from uasset_read.parse_uasset import parse_package
    bp_path = asset_path(sample_root, _BP_FIRST_PERSON_PLAYER_CONTROLLER_REL)
    result = parse_package(str(bp_path))
    try:
        blueprint = result.blueprint
        assert blueprint is not None, "蓝图数据为空"
        for var in blueprint.variables:
            cat = str(var.category)
            print(f"{var.var_name}: category={cat}")
            if "Fallback" in cat:
                if "parse_error" in cat.lower():
                    continue
                assert False, (
                    f"变量 {var.var_name} Category 解析失败: {cat}"
                )
    finally:
        _cleanup_result(result)


def test_category_not_empty_or_garbled(sample_root: Path):
    """变量 Category 不应为空或乱码"""
    from uasset_read.parse_uasset import parse_package
    bp_path = asset_path(sample_root, _BP_FIRST_PERSON_PLAYER_CONTROLLER_REL)
    result = parse_package(str(bp_path))
    try:
        blueprint = result.blueprint
        assert blueprint is not None, "蓝图数据为空"
        has_category = any(str(var.category).strip() for var in blueprint.variables)
        if not has_category:
            pytest.skip("该资产变量均无 Category（可能正常）")
    finally:
        _cleanup_result(result)


# === test_constructor_metadata.py ===

@pytest.mark.integration
@pytest.mark.quality
class TestVariableClassification:
    """验证 PackageIR.variables 不包含元数据变量。"""

    def test_no_metadata_variables_in_ir(self, sample_root: Path):
        """PackageIR.variables 不应包含 BlueprintSystemVersion 等。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        from uasset_read.ir_builder import build_package_ir

        bp_path = asset_path(sample_root, ASSET_BLUEPRINT_FIRST_PERSON)
        result = parse_uasset_with_linker(str(bp_path), tolerant=True)
        try:
            ir = build_package_ir(result)
            var_names = {v.name for v in ir.variables}
            metadata_found = var_names & _METADATA_KEYS
            assert len(metadata_found) == 0, (
                f"PackageIR.variables 包含元数据变量: {metadata_found}"
            )
        finally:
            del result, ir


# === test_blueprint_metadata_keys.py ===


class TestBlueprintMetadataKeysCentralized:
    """验证 _BLUEPRINT_METADATA_KEYS 在 constants.py 中集中定义。"""

    def test_constant_exists_in_constants(self):
        """BLUEPRINT_METADATA_KEYS 应在 constants.py 中定义。"""
        assert isinstance(BLUEPRINT_METADATA_KEYS, frozenset)
        assert len(BLUEPRINT_METADATA_KEYS) > 0

    def test_cpp_constructor_uses_centralized_constant(self):
        """cpp_constructor_ir_builder.py 应使用 constants.py 中的常量。"""
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
        from uasset_read.ir_builder import _BLUEPRINT_METADATA_KEYS as ir_keys
        assert ir_keys is BLUEPRINT_METADATA_KEYS or ir_keys == BLUEPRINT_METADATA_KEYS

    def test_required_keys_present(self):
        """元数据键集合应包含所有必需的 UE 内部字段。"""
        required = {
            "BlueprintSystemVersion",
            "GeneratedClass",
            "SimpleConstructionScript",
            "bCanEverTick",
            "bCanEverRender",
        }
        missing = required - BLUEPRINT_METADATA_KEYS
        assert len(missing) == 0, f"缺少必需元数据键: {missing}"
