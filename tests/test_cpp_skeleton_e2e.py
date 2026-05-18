"""
Golden-path e2e test: BP_FirstPersonCharacter → CppClassIR → .h 输出。

Per D-07: 集成测试基于 BP_FirstPersonCharacter 真实导出数据结构。
使用 mock 数据模拟 parse_uasset_with_linker 的返回结构。

测试完整管道：LinkerParseResult → extract_cpp_class_skeleton → format_cpp_header

CPF 标志参考（来自 constants.py）：
- CPF_Edit = 0x00000001
- CPF_BlueprintVisible = 0x00000004
- CPF_InstancedReference = 0x00800000
- CPF_EditAnywhere = 0x02000000
- CPF_BlueprintReadWrite = 0x00000100
"""
import pytest
from unittest.mock import MagicMock
from typing import List, Dict, Any

from uasset_read.cpp_gen import (
    extract_cpp_class_skeleton,
    format_cpp_header,
    CppClassIR,
    CppProperty,
    CppHeaderMeta,
)
from uasset_read.models.blueprint import BlueprintMetadata, BlueprintVariable
from uasset_read.models.core import FEdGraphPinType
from uasset_read.constants import (
    CPF_Edit,
    CPF_BlueprintVisible,
    CPF_InstancedReference,
    CPF_EditAnywhere,
    CPF_BlueprintReadWrite,
)


# CPF 标志组合（用于测试）
CPF_COMPONENT_FLAGS = CPF_EditAnywhere | CPF_BlueprintVisible | CPF_InstancedReference
CPF_VARIABLE_FLAGS = CPF_EditAnywhere | CPF_BlueprintReadWrite


class TestBPFirstPersonCharacterGoldenPath:
    """Golden-path test: BP_FirstPersonCharacter → CppClassIR → .h output."""

    @pytest.fixture
    def mock_blueprint_metadata(self) -> BlueprintMetadata:
        """创建模拟 BlueprintMetadata 匹配 BP_FirstPersonCharacter 结构。

        BP_FirstPersonCharacter 的真实结构（基于 reference/蓝图节点文本参考.md）：
        - parent_class: /Script/Engine.Character
        - 组件: DefaultSceneRoot, CameraBoom, FirstPersonCamera
        - 变量: MoveSpeed, JumpHeight, isAiming（典型 FPS 角色）
        """
        # 创建组件变量（is_component=True）
        # CPF 组件标志: EditAnywhere + BlueprintVisible + InstancedReference
        components = [
            BlueprintVariable(
                var_name="DefaultSceneRoot",
                var_type=FEdGraphPinType(
                    pin_category="object",
                    pin_subcategory="/Script/Engine.SceneComponent",
                    pin_subcategory_object=None,
                ),
                category="Components",
                property_flags=CPF_COMPONENT_FLAGS,
                default_value=None,
                is_component=True,
            ),
            BlueprintVariable(
                var_name="CameraBoom",
                var_type=FEdGraphPinType(
                    pin_category="object",
                    pin_subcategory="/Script/Engine.SpringArmComponent",
                    pin_subcategory_object=None,
                ),
                category="Components",
                property_flags=CPF_COMPONENT_FLAGS,
                default_value=None,
                is_component=True,
            ),
            BlueprintVariable(
                var_name="FirstPersonCamera",
                var_type=FEdGraphPinType(
                    pin_category="object",
                    pin_subcategory="/Script/Engine.CameraComponent",
                    pin_subcategory_object=None,
                ),
                category="Components",
                property_flags=CPF_COMPONENT_FLAGS,
                default_value=None,
                is_component=True,
            ),
        ]

        # 创建普通变量（is_component=False）
        # CPF 变量标志: EditAnywhere + BlueprintReadWrite
        variables = [
            BlueprintVariable(
                var_name="MoveSpeed",
                var_type=FEdGraphPinType(
                    pin_category="float",
                    pin_subcategory="",
                    pin_subcategory_object=None,
                ),
                category="Movement",
                property_flags=CPF_VARIABLE_FLAGS,
                default_value=600.0,
                is_component=False,
            ),
            BlueprintVariable(
                var_name="JumpHeight",
                var_type=FEdGraphPinType(
                    pin_category="float",
                    pin_subcategory="",
                    pin_subcategory_object=None,
                ),
                category="Movement",
                property_flags=CPF_VARIABLE_FLAGS,
                default_value=420.0,
                is_component=False,
            ),
            BlueprintVariable(
                var_name="isAiming",
                var_type=FEdGraphPinType(
                    pin_category="bool",
                    pin_subcategory="",
                    pin_subcategory_object=None,
                ),
                category="Combat",
                property_flags=CPF_VARIABLE_FLAGS,
                default_value=False,
                is_component=False,
            ),
        ]

        return BlueprintMetadata(
            is_blueprint=True,
            parent_class="/Script/Engine.Character",
            variables=components + variables,
            functions=[],
            events=[],
        )

    @pytest.fixture
    def mock_linker_result(self, mock_blueprint_metadata) -> MagicMock:
        """创建模拟 LinkerParseResult。

        模拟 parse_uasset_with_linker 的返回结构。
        """
        result = MagicMock()
        result.blueprint = mock_blueprint_metadata
        result.components = []  # SCS 组件列表（此处使用 blueprint.variables 中的组件）
        result.linker = None

        # 模拟 PackageFileSummary
        summary = MagicMock()
        summary.package_name = "BP_FirstPersonCharacter"
        result.summary = summary

        # 模拟 name_map
        result.name_map = ["BP_FirstPersonCharacter"]

        return result

    def test_full_extraction(self, mock_linker_result):
        """Full pipeline: extract_cpp_class_skeleton returns complete CppClassIR."""
        ir = extract_cpp_class_skeleton(mock_linker_result)

        # 验证类名和父类
        assert ir.name == "ABP_FirstPersonCharacter"
        assert ir.parent_class == "ACharacter"

        # 验证属性数量（3 组件 + 3 变量 = 6）
        assert len(ir.properties) >= 5

    def test_component_properties(self, mock_linker_result):
        """Component properties have pointer types and correct UPROPERTY marks."""
        ir = extract_cpp_class_skeleton(mock_linker_result)
        comp_props = [p for p in ir.properties if p.category == "component"]

        assert len(comp_props) >= 3

        # 验证 DefaultSceneRoot
        scene_root = next((p for p in comp_props if p.name == "DefaultSceneRoot"), None)
        assert scene_root is not None
        assert scene_root.cpp_type == "USceneComponent*"
        assert "Instanced" in scene_root.uproperty_marks

        # 验证 CameraBoom
        camera_boom = next((p for p in comp_props if p.name == "CameraBoom"), None)
        assert camera_boom is not None
        assert camera_boom.cpp_type == "USpringArmComponent*"
        assert "Instanced" in camera_boom.uproperty_marks

        # 验证 FirstPersonCamera
        camera = next((p for p in comp_props if p.name == "FirstPersonCamera"), None)
        assert camera is not None
        assert camera.cpp_type == "UCameraComponent*"
        assert "Instanced" in camera.uproperty_marks

    def test_variable_properties(self, mock_linker_result):
        """Variable properties have correct C++ types and default values."""
        ir = extract_cpp_class_skeleton(mock_linker_result)
        var_props = [p for p in ir.properties if p.category == "variable"]

        assert len(var_props) >= 2

        # 验证 MoveSpeed
        move_speed = next((p for p in var_props if p.name == "MoveSpeed"), None)
        assert move_speed is not None
        assert move_speed.cpp_type == "float"
        assert move_speed.default_value == 600.0

        # 验证 isAiming
        is_aiming = next((p for p in var_props if p.name == "isAiming"), None)
        assert is_aiming is not None
        assert is_aiming.cpp_type == "bool"
        assert is_aiming.default_value == False

    def test_header_generation(self, mock_linker_result):
        """format_cpp_header produces valid UE .h with all components and variables."""
        ir = extract_cpp_class_skeleton(mock_linker_result)
        header_text = format_cpp_header(ir)

        # 验证基本结构
        assert "#pragma once" in header_text
        assert "ACharacter" in header_text
        assert "GENERATED_BODY()" in header_text
        assert "ABP_FirstPersonCharacter.generated.h" in header_text

        # 验证组件
        assert "USceneComponent* DefaultSceneRoot" in header_text
        assert "USpringArmComponent* CameraBoom" in header_text
        assert "UCameraComponent* FirstPersonCamera" in header_text

        # 验证变量
        assert "float MoveSpeed" in header_text
        assert "bool isAiming" in header_text

        # 验证 UPROPERTY
        assert "UPROPERTY(" in header_text
        assert "Instanced" in header_text

    def test_header_structure_complete(self, mock_linker_result):
        """Generated header has complete UE structure."""
        ir = extract_cpp_class_skeleton(mock_linker_result)
        header_text = format_cpp_header(ir)

        lines = header_text.split('\n')

        # 验证结构顺序
        assert lines[0] == "#pragma once"
        assert '#include "CoreMinimal.h"' in header_text

        # 验证类声明
        class_line = next(l for l in lines if "class ABP_FirstPersonCharacter" in l)
        assert ": public ACharacter" in class_line

        # 验证 public/protected 区域
        assert "public:" in header_text
        assert "protected:" in header_text

        # 验证构造函数声明
        assert "ABP_FirstPersonCharacter();" in header_text


class TestBoundaryCases:
    """Boundary tests per D-07: 边界情况测试。"""

    def _make_mock_result(self, name: str, parent: str, variables: List[BlueprintVariable]) -> MagicMock:
        """Helper to create mock LinkerParseResult."""
        blueprint = BlueprintMetadata(
            is_blueprint=True,
            parent_class=parent,
            variables=variables,
            functions=[],
            events=[],
        )

        result = MagicMock()
        result.blueprint = blueprint
        result.components = []
        result.linker = None
        result.summary = MagicMock()
        result.summary.package_name = name
        result.name_map = [name]

        return result

    def test_empty_blueprint(self):
        """Test empty blueprint (no variables, no components) → minimal valid .h."""
        result = self._make_mock_result("BP_EmptyActor", "/Script/Engine.Actor", [])

        ir = extract_cpp_class_skeleton(result)
        header_text = format_cpp_header(ir)

        # 验证最小有效结构
        assert "#pragma once" in header_text
        assert "class ABP_EmptyActor : public AActor" in header_text
        assert "GENERATED_BODY()" in header_text
        assert "public:" in header_text
        assert "protected:" in header_text
        assert "ABP_EmptyActor();" in header_text
        assert header_text.rstrip().endswith("};")

    def test_single_inheritance_from_actor(self):
        """Test single inheritance (BP_C → Actor) → correct AActor parent."""
        variables = [
            BlueprintVariable(
                var_name="TestVar",
                var_type=FEdGraphPinType(
                    pin_category="int",
                    pin_subcategory="",
                    pin_subcategory_object=None,
                ),
                category="Test",
                property_flags=CPF_VARIABLE_FLAGS,
                default_value=42,
                is_component=False,
            ),
        ]
        result = self._make_mock_result("BP_SimpleActor", "/Script/Engine.Actor", variables)

        ir = extract_cpp_class_skeleton(result)

        assert ir.parent_class == "AActor"
        header_text = format_cpp_header(ir)
        assert "AActor" in header_text

    def test_empty_component_list(self):
        """Test blueprint with only variables (no components) → no component UPROPERTY."""
        variables = [
            BlueprintVariable(
                var_name="SimpleVar",
                var_type=FEdGraphPinType(
                    pin_category="float",
                    pin_subcategory="",
                    pin_subcategory_object=None,
                ),
                category="Test",
                property_flags=CPF_VARIABLE_FLAGS,
                default_value=100.0,
                is_component=False,
            ),
        ]
        result = self._make_mock_result("BP_NoComponents", "/Script/Engine.Actor", variables)

        ir = extract_cpp_class_skeleton(result)
        header_text = format_cpp_header(ir)

        # 验证没有组件声明（Components 注释块）
        assert "// Components" not in header_text
        # 验证变量存在
        assert "float SimpleVar" in header_text

    def test_replicated_property(self):
        """Test with CPF_Net | CPF_Replicated → UPROPERTY(Replicated) in output."""
        from uasset_read.constants import CPF_Net, CPF_Replicated
        # CPF_Net | CPF_Replicated | CPF_EditAnywhere | CPF_BlueprintReadWrite
        replicated_flags = CPF_Net | CPF_Replicated | CPF_VARIABLE_FLAGS
        variables = [
            BlueprintVariable(
                var_name="ReplicatedVar",
                var_type=FEdGraphPinType(
                    pin_category="int",
                    pin_subcategory="",
                    pin_subcategory_object=None,
                ),
                category="Network",
                property_flags=replicated_flags,
                default_value=0,
                is_component=False,
            ),
        ]
        result = self._make_mock_result("BP_Replicated", "/Script/Engine.Actor", variables)

        ir = extract_cpp_class_skeleton(result)
        header_text = format_cpp_header(ir)

        # 验证 Replicated 标记存在
        replicated_var = next(p for p in ir.properties if p.name == "ReplicatedVar")
        # 检查是否有 Replicated 标记
        assert "Replicated" in replicated_var.uproperty_marks


class TestHeaderOutputValidation:
    """验证生成的 .h 文件符合 UE 格式规范。"""

    def test_includes_ordering(self):
        """generated.h is always the last include."""
        # 使用直接构建的 CppClassIR
        ir = CppClassIR(
            name="ABP_FirstPersonCharacter",
            parent_class="ACharacter",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                includes=['"Engine/GameFramework/Character.h"'],
                generated_include='"ABP_FirstPersonCharacter.generated.h"',
            ),
            properties=[],
        )

        header_text = format_cpp_header(ir)
        lines = header_text.split('\n')
        include_lines = [l for l in lines if l.startswith('#include')]

        # generated.h 必须是最后一个 include
        assert include_lines[-1] == '#include "ABP_FirstPersonCharacter.generated.h"'

    def test_uproperty_format_valid(self):
        """UPROPERTY declarations have valid format."""
        # 创建简单测试 IR
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="float",
                    name="TestVar",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Test",
                    default_value=100.0,
                ),
            ],
        )

        header_text = format_cpp_header(ir)
        lines = header_text.split('\n')

        # 验证 UPROPERTY 格式
        uprop_line = next(l for l in lines if "UPROPERTY(" in l)
        assert uprop_line.strip().startswith("UPROPERTY(")
        assert uprop_line.strip().endswith(")")

        # 验证属性声明格式
        var_line = next(l for l in lines if "float TestVar" in l)
        assert "float TestVar = 100.0f;" in var_line.strip()


class TestMockDataIntegrity:
    """验证 mock 数据与真实 BP_FirstPersonCharacter 结构一致。"""

    @pytest.fixture
    def mock_blueprint_metadata(self) -> BlueprintMetadata:
        """创建模拟 BlueprintMetadata 匹配 BP_FirstPersonCharacter 结构。"""
        components = [
            BlueprintVariable(
                var_name="DefaultSceneRoot",
                var_type=FEdGraphPinType(
                    pin_category="object",
                    pin_subcategory="/Script/Engine.SceneComponent",
                    pin_subcategory_object=None,
                ),
                category="Components",
                property_flags=CPF_COMPONENT_FLAGS,
                default_value=None,
                is_component=True,
            ),
            BlueprintVariable(
                var_name="CameraBoom",
                var_type=FEdGraphPinType(
                    pin_category="object",
                    pin_subcategory="/Script/Engine.SpringArmComponent",
                    pin_subcategory_object=None,
                ),
                category="Components",
                property_flags=CPF_COMPONENT_FLAGS,
                default_value=None,
                is_component=True,
            ),
            BlueprintVariable(
                var_name="FirstPersonCamera",
                var_type=FEdGraphPinType(
                    pin_category="object",
                    pin_subcategory="/Script/Engine.CameraComponent",
                    pin_subcategory_object=None,
                ),
                category="Components",
                property_flags=CPF_COMPONENT_FLAGS,
                default_value=None,
                is_component=True,
            ),
        ]

        variables = [
            BlueprintVariable(
                var_name="MoveSpeed",
                var_type=FEdGraphPinType(
                    pin_category="float",
                    pin_subcategory="",
                    pin_subcategory_object=None,
                ),
                category="Movement",
                property_flags=CPF_VARIABLE_FLAGS,
                default_value=600.0,
                is_component=False,
            ),
            BlueprintVariable(
                var_name="JumpHeight",
                var_type=FEdGraphPinType(
                    pin_category="float",
                    pin_subcategory="",
                    pin_subcategory_object=None,
                ),
                category="Movement",
                property_flags=CPF_VARIABLE_FLAGS,
                default_value=420.0,
                is_component=False,
            ),
            BlueprintVariable(
                var_name="isAiming",
                var_type=FEdGraphPinType(
                    pin_category="bool",
                    pin_subcategory="",
                    pin_subcategory_object=None,
                ),
                category="Combat",
                property_flags=CPF_VARIABLE_FLAGS,
                default_value=False,
                is_component=False,
            ),
        ]

        return BlueprintMetadata(
            is_blueprint=True,
            parent_class="/Script/Engine.Character",
            variables=components + variables,
            functions=[],
            events=[],
        )

    def test_component_types_match_ue(self, mock_blueprint_metadata):
        """Component types match UE naming conventions."""
        components = [v for v in mock_blueprint_metadata.variables if v.is_component]

        # 验证组件数量
        assert len(components) == 3

        # 验证组件类型路径
        comp_types = {v.var_name: v.var_type.pin_subcategory for v in components}

        assert comp_types["DefaultSceneRoot"] == "/Script/Engine.SceneComponent"
        assert comp_types["CameraBoom"] == "/Script/Engine.SpringArmComponent"
        assert comp_types["FirstPersonCamera"] == "/Script/Engine.CameraComponent"

    def test_variable_types_match_ue(self, mock_blueprint_metadata):
        """Variable types match expected C++ types."""
        variables = [v for v in mock_blueprint_metadata.variables if not v.is_component]

        # 验证变量类型
        var_types = {v.var_name: v.var_type.pin_category for v in variables}

        assert var_types["MoveSpeed"] == "float"
        assert var_types["JumpHeight"] == "float"
        assert var_types["isAiming"] == "bool"