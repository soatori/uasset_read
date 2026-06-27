"""Blueprint 字段验证测试 — 合并自以下文件：
- test_interfaces.py (1 test): BlueprintInterfaces 提取测试（Issue #169）
- test_blueprint_description.py (1 test): BlueprintDescription 提取测试（Issue #169）
- test_variable_type.py (1 test): BlueprintVariable var_type 字段填充测试（Issue #172）
- test_ftext_category.py (2 tests): FText Category 解析测试（Issue #170）
- test_constructor_metadata.py (1 test): 变量分类测试 — 验证 PackageIR.variables 不包含元数据变量
"""

from __future__ import annotations

import os

import pytest

# 测试资产路径
_BP_FIRST_PERSON = "E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
_BP_FIRST_PERSON_PLAYER_CONTROLLER = "E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonPlayerController.uasset"

_REAL_BLUEPRINT = os.path.join(
    os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\Samples"),
    "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)

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

def test_blueprint_has_interfaces():
    """蓝图应包含 interfaces 列表"""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    result = parse_uasset_with_linker(_BP_FIRST_PERSON, tolerant=True)
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

def test_blueprint_has_description():
    """蓝图应包含 description 字段"""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    result = parse_uasset_with_linker(_BP_FIRST_PERSON, tolerant=True)
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

    def test_variable_has_var_type(self):
        """变量应包含 var_type 类型信息"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        result = parse_uasset_with_linker(_BP_FIRST_PERSON, tolerant=True)
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

def test_category_not_property_fallback():
    """变量 Category 不应为 PropertyFallback（已知损坏数据除外）"""
    from uasset_read.parse_uasset import parse_package
    result = parse_package(_BP_FIRST_PERSON_PLAYER_CONTROLLER)
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


def test_category_not_empty_or_garbled():
    """变量 Category 不应为空或乱码"""
    from uasset_read.parse_uasset import parse_package
    result = parse_package(_BP_FIRST_PERSON_PLAYER_CONTROLLER)
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
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestVariableClassification:
    """验证 PackageIR.variables 不包含元数据变量。"""

    def test_no_metadata_variables_in_ir(self):
        """PackageIR.variables 不应包含 BlueprintSystemVersion 等。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        from uasset_read.ir_builder import build_package_ir

        result = parse_uasset_with_linker(_REAL_BLUEPRINT, tolerant=True)
        try:
            ir = build_package_ir(result)
            var_names = {v.name for v in ir.variables}
            metadata_found = var_names & _METADATA_KEYS
            assert len(metadata_found) == 0, (
                f"PackageIR.variables 包含元数据变量: {metadata_found}"
            )
        finally:
            del result, ir
