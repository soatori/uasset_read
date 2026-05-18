"""
extract_cpp_class_skeleton() 单元测试。

Phase 56: 测试 C++ 类骨架提取逻辑。

测试覆盖：
1. full blueprint → CppClassIR with name, parent_class, properties
2. blueprint with no variables → properties is empty list, not None
3. single inheritance chain → parent_class = "ACharacter"
4. component-only blueprint → properties contains component CppProperty entries
5. variable-only blueprint → properties contains variable CppProperty entries
6. header_meta.includes contains parent class header path
7. header_meta.generated_include matches class name + ".generated.h"
8. methods is empty list, constructor has empty sub-arrays
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, PropertyMock
from typing import List, Dict, Any, Optional

from uasset_read.link.result import LinkerParseResult
from uasset_read.models.blueprint import BlueprintMetadata, BlueprintVariable
from uasset_read.models.core import FEdGraphPinType
from uasset_read.cpp_gen.formatters import CppClassIR, CppProperty
from uasset_read.cpp_gen.extract_cpp_skeleton import extract_cpp_class_skeleton


# ============================================================================
# Mock 辅助函数
# ============================================================================

def create_mock_result(
    package_name: str = "BP_FirstPersonCharacter",
    parent_class: str = "/Script/Engine.Character",
    variables: List[BlueprintVariable] = None,
    components: List[Dict] = None,
) -> MagicMock:
    """创建模拟 LinkerParseResult。"""
    result = MagicMock(spec=LinkerParseResult)

    # Mock summary
    summary = MagicMock()
    summary.package_name = package_name
    result.summary = summary

    # Mock blueprint
    blueprint = MagicMock(spec=BlueprintMetadata)
    blueprint.is_blueprint = True
    blueprint.parent_class = parent_class
    blueprint.variables = variables or []
    blueprint.functions = []
    blueprint.events = []
    result.blueprint = blueprint

    # Mock components list
    result.components = components or []

    # Mock linker (not needed for basic tests)
    result.linker = None
    result.name_map = [package_name]

    return result


def create_mock_variable(
    name: str,
    pin_category: str = "float",
    pin_subcategory: str = "",
    is_component: bool = False,
    property_flags: int = 0,
    default_value: Any = None,
    category: str = "Default",
) -> BlueprintVariable:
    """创建模拟 BlueprintVariable。"""
    var_type = MagicMock(spec=FEdGraphPinType)
    var_type.pin_category = pin_category
    var_type.pin_subcategory = pin_subcategory
    var_type.container_type = 0
    var_type.is_reference = False

    return BlueprintVariable(
        var_name=name,
        var_type=var_type,
        category=category,
        property_flags=property_flags,
        default_value=default_value,
        is_component=is_component,
    )


# ============================================================================
# 测试用例（TDD RED）
# ============================================================================

class TestExtractCppSkeleton:
    """extract_cpp_class_skeleton() 测试类。"""

    def test_full_blueprint_returns_cpp_class_ir(self):
        """Test 1: full blueprint returns CppClassIR with name, parent_class, properties"""
        # 创建带变量的蓝图
        variables = [
            create_mock_variable("MoveSpeed", "float", "", False, 0x00000005, 100.0),
            create_mock_variable("DefaultSceneRoot", "object", "SceneComponent", True, 0x00080000),
        ]

        result = create_mock_result(
            package_name="BP_FirstPersonCharacter",
            parent_class="/Script/Engine.Character",
            variables=variables,
        )

        ir = extract_cpp_class_skeleton(result)

        # 验证返回类型
        assert isinstance(ir, CppClassIR)
        assert ir.name == "ABP_FirstPersonCharacter"  # A 前缀（Actor 派生）
        assert ir.parent_class == "ACharacter"
        assert len(ir.properties) == 2

    def test_blueprint_no_variables_empty_properties(self):
        """Test 2: blueprint with no variables → properties is empty list, not None"""
        result = create_mock_result(
            package_name="BP_Empty",
            parent_class="/Script/Engine.Actor",
            variables=[],
        )

        ir = extract_cpp_class_skeleton(result)

        # properties 必须是空列表，不是 None
        assert ir.properties is not None
        assert ir.properties == []
        assert isinstance(ir.properties, list)

    def test_single_inheritance_chain(self):
        """Test 3: single inheritance chain -> parent_class = ACharacter"""
        result = create_mock_result(
            package_name="BP_Character",
            parent_class="/Script/Engine.Character",
        )

        ir = extract_cpp_class_skeleton(result)

        assert ir.parent_class == "ACharacter"

    def test_component_only_blueprint(self):
        """Test 4: component-only blueprint → properties contains component CppProperty"""
        variables = [
            create_mock_variable("CameraComp", "object", "CameraComponent", True, 0x00080000),
            create_mock_variable("SpringArmComp", "object", "SpringArmComponent", True, 0x00080000),
        ]

        result = create_mock_result(
            package_name="BP_CameraRig",
            parent_class="/Script/Engine.Actor",
            variables=variables,
        )

        ir = extract_cpp_class_skeleton(result)

        # 验证组件属性
        assert len(ir.properties) == 2
        for prop in ir.properties:
            assert isinstance(prop, CppProperty)
            assert prop.category == "component"
            # 组件类型必须带 * 指针
            assert prop.cpp_type.endswith("*")

    def test_variable_only_blueprint(self):
        """Test 5: variable-only blueprint → properties contains variable CppProperty"""
        variables = [
            create_mock_variable("Health", "float", "", False, 0x00000005, 100.0),
            create_mock_variable("IsAlive", "bool", "", False, 0x00000004, True),
        ]

        result = create_mock_result(
            package_name="BP_HealthComponent",
            parent_class="/Script/Engine.ActorComponent",
            variables=variables,
        )

        ir = extract_cpp_class_skeleton(result)

        # 验证变量属性
        assert len(ir.properties) == 2
        for prop in ir.properties:
            assert isinstance(prop, CppProperty)
            assert prop.category == "variable"

    def test_header_meta_includes_parent_class(self):
        """Test 6: header_meta.includes contains parent class header path"""
        result = create_mock_result(
            package_name="BP_Character",
            parent_class="/Script/Engine.Character",
        )

        ir = extract_cpp_class_skeleton(result)

        # 父类是 ACharacter → 应包含 Character.h
        assert len(ir.header_meta.includes) > 0
        # 检查是否包含 Character.h 路径
        has_character_include = any(
            "Character" in inc for inc in ir.header_meta.includes
        )
        assert has_character_include

    def test_generated_include_matches_class_name(self):
        """Test 7: header_meta.generated_include matches class name + .generated.h"""
        result = create_mock_result(
            package_name="BP_FirstPerson",
            parent_class="/Script/Engine.Character",
        )

        ir = extract_cpp_class_skeleton(result)

        # generated_include 应为 "ABP_FirstPerson.generated.h"
        assert ir.header_meta.generated_include == '"ABP_FirstPerson.generated.h"'

    def test_methods_empty_constructor_empty(self):
        """Test 8: methods is empty list, constructor has empty sub-arrays"""
        result = create_mock_result(
            package_name="BP_Test",
            parent_class="/Script/Engine.Actor",
        )

        ir = extract_cpp_class_skeleton(result)

        # methods 必须为空列表（Phase 56）
        assert ir.methods == []
        assert isinstance(ir.methods, list)

        # constructor 子数组必须为空（Phase 56）
        assert ir.constructor["component_creations"] == []
        assert ir.constructor["component_assignments"] == []
        assert ir.constructor["default_values"] == []

    def test_uproperty_marks_for_component(self):
        """Test: component properties get correct UPROPERTY marks (Instanced + Visible)"""
        from uasset_read.constants import CPF_InstancedReference

        variables = [
            create_mock_variable("SceneRoot", "object", "SceneComponent", True, CPF_InstancedReference),
        ]

        result = create_mock_result(
            package_name="BP_Test",
            parent_class="/Script/Engine.Actor",
            variables=variables,
        )

        ir = extract_cpp_class_skeleton(result)

        # 组件应包含 Instanced 标记
        prop = ir.properties[0]
        assert "Instanced" in prop.uproperty_marks

    def test_class_name_prefix_for_component_blueprint(self):
        """Test: Component-derived blueprint gets U prefix instead of A"""
        result = create_mock_result(
            package_name="BP_MyComponent",
            parent_class="/Script/Engine.ActorComponent",
        )

        ir = extract_cpp_class_skeleton(result)

        # ActorComponent 派生类应使用 U 前缀
        assert ir.name.startswith("U")
        assert ir.parent_class == "UActorComponent"


# ============================================================================
# 运行入口
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])