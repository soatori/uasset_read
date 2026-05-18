"""
单元测试 — cpp_constructor_ir_builder 模块（Phase 59 Plan 01）。

覆盖：
- CppComponentCreation, CppComponentAssignment, CppDefaultValue 数据模型
- build_component_creations: 从 ir.properties 提取组件创建，跳过 UInputAction*
- build_component_assignments: 从 components 数据提取 attach 关系
- build_default_values: 从变量属性提取默认值，InputAction 标记 needs_load_object
- build_transform_assignments: 从 component transforms 提取变换数据
- _sanitize_value: 注入字符清理
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from uasset_read.cpp_gen.cpp_constructor_ir_builder import (
    CppComponentCreation,
    CppComponentAssignment,
    CppDefaultValue,
    build_component_creations,
    build_component_assignments,
    build_default_values,
    build_transform_assignments,
    _sanitize_value,
    _blueprint_var_type_to_cpp,
)


# ============================================================================
# Test fixtures / helpers
# ============================================================================


class MockPinType:
    """Minimal FEdGraphPinType mock for tests."""
    def __init__(self, category="", subcategory=""):
        self.pin_category = category
        self.pin_subcategory = subcategory
        self.pin_subcategory_object = None
        self.container_type = 0


class MockCppProperty:
    """Minimal CppProperty mock for tests."""
    def __init__(
        self,
        cpp_type: str,
        name: str,
        category: str,
        default_value=None,
        uproperty_marks=None,
    ):
        self.cpp_type = cpp_type
        self.name = name
        self.category = category
        self.default_value = default_value
        self.uproperty_marks = uproperty_marks or []
        self.cpp_comment = ""


class MockBlueprintVariable:
    """Minimal BlueprintVariable mock for tests."""
    def __init__(
        self,
        var_name: str,
        var_type=None,
        default_value=None,
        is_component: bool = False,
    ):
        self.var_name = var_name
        self.var_type = var_type or MockPinType("float")
        self.default_value = default_value
        self.is_component = is_component


class MockCppClassIR:
    """Minimal CppClassIR mock for tests."""
    def __init__(self, name="TestClass", properties=None):
        self.name = name
        self.parent_class = "APawn"
        self.properties = properties or []
        self.header_meta = None
        self.methods = []
        self.constructor = {
            "component_creations": [],
            "component_assignments": [],
            "default_values": [],
        }


# ============================================================================
# Data model tests
# ============================================================================


class TestCppComponentCreation:
    def test_basic_creation(self):
        c = CppComponentCreation(
            variable_name="FirstPersonMesh",
            cpp_type="USkeletalMeshComponent",
            component_name="FirstPersonMesh",
        )
        assert c.variable_name == "FirstPersonMesh"
        assert c.cpp_type == "USkeletalMeshComponent"
        assert c.component_name == "FirstPersonMesh"

    def test_to_dict(self):
        c = CppComponentCreation(
            variable_name="Cam",
            cpp_type="UCameraComponent",
            component_name="Cam",
        )
        d = c.to_dict()
        assert d == {
            "variable_name": "Cam",
            "cpp_type": "UCameraComponent",
            "component_name": "Cam",
        }


class TestCppComponentAssignment:
    def test_basic_assignment(self):
        a = CppComponentAssignment(
            child_name="Camera",
            parent_name="Mesh",
            socket_name="head",
        )
        assert a.child_name == "Camera"
        assert a.parent_name == "Mesh"
        assert a.socket_name == "head"

    def test_empty_socket(self):
        a = CppComponentAssignment(
            child_name="Camera",
            parent_name="Mesh",
        )
        assert a.socket_name == ""

    def test_to_dict(self):
        a = CppComponentAssignment(
            child_name="Cam",
            parent_name="RootComponent",
        )
        d = a.to_dict()
        assert d == {
            "child_name": "Cam",
            "parent_name": "RootComponent",
            "socket_name": "",
        }


class TestCppDefaultValue:
    def test_basic_default(self):
        d = CppDefaultValue(
            target="MoveSpeed",
            value="100.0f",
            cpp_type="float",
        )
        assert d.target == "MoveSpeed"
        assert d.value == "100.0f"
        assert d.cpp_type == "float"
        assert d.is_method_call is False
        assert d.method_type == ""
        assert d.needs_load_object is False

    def test_method_call(self):
        d = CppDefaultValue(
            target="Capsule",
            value={"relative_location": {"X": 0, "Y": 0, "Z": 88}},
            cpp_type="transform",
            is_method_call=True,
            method_type="transform",
        )
        assert d.is_method_call is True
        assert d.method_type == "transform"

    def test_load_object(self):
        d = CppDefaultValue(
            target="IA_Jump",
            value="/Game/Inputs/IA_Jump",
            cpp_type="UInputAction*",
            needs_load_object=True,
        )
        assert d.needs_load_object is True

    def test_to_dict_minimal(self):
        d = CppDefaultValue(target="X", value="1", cpp_type="int32")
        assert d.to_dict() == {"target": "X", "value": "1", "cpp_type": "int32"}

    def test_to_dict_with_flags(self):
        d = CppDefaultValue(
            target="T",
            value="V",
            cpp_type="transform",
            is_method_call=True,
            method_type="transform",
            needs_load_object=True,
        )
        dt = d.to_dict()
        assert dt["is_method_call"] is True
        assert dt["method_type"] == "transform"
        assert dt["needs_load_object"] is True


# ============================================================================
# build_component_creations tests
# ============================================================================


class TestBuildComponentCreations:
    def test_single_component(self):
        ir = MockCppClassIR(properties=[
            MockCppProperty("USkeletalMeshComponent*", "FirstPersonMesh", "component"),
        ])
        creations = build_component_creations(ir)
        assert len(creations) == 1
        assert creations[0].variable_name == "FirstPersonMesh"
        assert creations[0].cpp_type == "USkeletalMeshComponent"
        assert creations[0].component_name == "FirstPersonMesh"

    def test_multiple_components(self):
        ir = MockCppClassIR(properties=[
            MockCppProperty("USkeletalMeshComponent*", "Mesh", "component"),
            MockCppProperty("UCameraComponent*", "Camera", "component"),
            MockCppProperty("USpringArmComponent*", "Arm", "component"),
        ])
        creations = build_component_creations(ir)
        assert len(creations) == 3

    def test_skip_input_action(self):
        """UInputAction* should NOT generate CreateDefaultSubobject."""
        ir = MockCppClassIR(properties=[
            MockCppProperty("USkeletalMeshComponent*", "Mesh", "component"),
            MockCppProperty("UInputAction*", "IA_JumpAction", "component"),
            MockCppProperty("UInputAction*", "IA_MoveAction", "component"),
        ])
        creations = build_component_creations(ir)
        assert len(creations) == 1
        assert creations[0].variable_name == "Mesh"

    def test_skip_variables(self):
        """category='variable' should not produce component creations."""
        ir = MockCppClassIR(properties=[
            MockCppProperty("float", "MoveSpeed", "variable", default_value=100.0),
            MockCppProperty("bool", "IsAlive", "variable", default_value=True),
        ])
        creations = build_component_creations(ir)
        assert len(creations) == 0

    def test_empty_properties(self):
        ir = MockCppClassIR(properties=[])
        creations = build_component_creations(ir)
        assert creations == []

    def test_strips_pointer_from_type(self):
        ir = MockCppClassIR(properties=[
            MockCppProperty("UArrowComponent*", "ArrowComponent", "component"),
        ])
        creations = build_component_creations(ir)
        assert creations[0].cpp_type == "UArrowComponent"


# ============================================================================
# build_component_assignments tests
# ============================================================================


class TestBuildComponentAssignments:
    def test_single_attachment(self):
        components = [
            {
                "name": "FirstPersonCameraComponent",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {},
                "attach_parent": "FirstPersonMesh",
                "attach_socket_name": "head",
            }
        ]
        assignments = build_component_assignments(components)
        assert len(assignments) == 1
        assert assignments[0].child_name == "FirstPersonCameraComponent"
        assert assignments[0].parent_name == "FirstPersonMesh"
        assert assignments[0].socket_name == "head"

    def test_root_parent_mapping(self):
        """'Root' or 'root' should map to 'RootComponent'."""
        components = [
            {
                "name": "Cam",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {},
                "attach_parent": "Root",
            }
        ]
        assignments = build_component_assignments(components)
        assert assignments[0].parent_name == "RootComponent"

    def test_empty_socket_default(self):
        components = [
            {
                "name": "Cam",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {},
                "attach_parent": "Mesh",
            }
        ]
        assignments = build_component_assignments(components)
        assert assignments[0].socket_name == ""

    def test_no_attach_parent_skipped(self):
        """Components without attach_parent should be skipped."""
        components = [
            {
                "name": "Mesh",
                "class": "SkeletalMeshComponent",
                "properties": {},
                "transforms": {},
            }
        ]
        assignments = build_component_assignments(components)
        assert len(assignments) == 0

    def test_attach_parent_alternate_keys(self):
        """Should support AttachParent (PascalCase) as well."""
        components = [
            {
                "name": "Cam",
                "class": "CameraComponent",
                "properties": {"AttachParent": "Mesh"},
                "transforms": {},
            }
        ]
        assignments = build_component_assignments(components)
        assert len(assignments) == 1
        assert assignments[0].parent_name == "Mesh"

    def test_empty_components(self):
        assignments = build_component_assignments([])
        assert assignments == []

    def test_multiple_attachments(self):
        components = [
            {
                "name": "Cam",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {},
                "attach_parent": "Mesh",
            },
            {
                "name": "Arm",
                "class": "SpringArmComponent",
                "properties": {},
                "transforms": {},
                "attach_parent": "RootComponent",
            },
        ]
        assignments = build_component_assignments(components)
        assert len(assignments) == 2


# ============================================================================
# build_default_values tests
# ============================================================================


class TestBuildDefaultValues:
    def test_variable_with_default(self):
        ir = MockCppClassIR(properties=[
            MockCppProperty("float", "MoveSpeed", "variable", default_value=100.0),
        ])
        defaults = build_default_values(ir)
        assert len(defaults) == 1
        assert defaults[0].target == "MoveSpeed"
        assert defaults[0].value == "100.0"
        assert defaults[0].cpp_type == "float"

    def test_skip_none_default(self):
        """Variables with None default_value should be skipped."""
        ir = MockCppClassIR(properties=[
            MockCppProperty("float", "MoveSpeed", "variable", default_value=None),
        ])
        defaults = build_default_values(ir)
        assert len(defaults) == 0

    def test_skip_components(self):
        """category='component' should not produce default values."""
        ir = MockCppClassIR(properties=[
            MockCppProperty("USkeletalMeshComponent*", "Mesh", "component"),
        ])
        defaults = build_default_values(ir)
        assert len(defaults) == 0

    def test_input_action_needs_load_object(self):
        """UInputAction* variables should have needs_load_object=True."""
        ir = MockCppClassIR(properties=[
            MockCppProperty(
                "UInputAction*",
                "IA_JumpAction",
                "variable",
                default_value="/Game/Inputs/IA_Jump.IA_Jump",
            ),
        ])
        defaults = build_default_values(ir)
        assert len(defaults) == 1
        assert defaults[0].target == "IA_JumpAction"
        assert defaults[0].needs_load_object is True

    def test_input_action_empty_default_skipped(self):
        """UInputAction* with empty default should be skipped."""
        ir = MockCppClassIR(properties=[
            MockCppProperty(
                "UInputAction*",
                "IA_JumpAction",
                "variable",
                default_value="",
            ),
        ])
        defaults = build_default_values(ir)
        assert len(defaults) == 0

    def test_from_blueprint_vars(self):
        """Should also extract from blueprint_vars parameter."""
        ir = MockCppClassIR(properties=[])
        bp_vars = [
            MockBlueprintVariable(
                var_name="MaxHealth",
                var_type=MockPinType("FloatProperty"),
                default_value=100.0,
            )
        ]
        defaults = build_default_values(ir, blueprint_vars=bp_vars)
        assert len(defaults) == 1
        assert defaults[0].target == "MaxHealth"

    def test_no_duplicate_from_bp_vars(self):
        """Variables already in ir.properties should not be duplicated from bp_vars."""
        ir = MockCppClassIR(properties=[
            MockCppProperty("float", "Speed", "variable", default_value=50.0),
        ])
        bp_vars = [
            MockBlueprintVariable(
                var_name="Speed",
                var_type=MockPinType("FloatProperty"),
                default_value=999.0,
            )
        ]
        defaults = build_default_values(ir, blueprint_vars=bp_vars)
        assert len(defaults) == 1
        assert defaults[0].value == "50.0"  # from ir.properties, not bp_vars

    def test_skip_component_bp_vars(self):
        """is_component=True bp_vars should be skipped."""
        ir = MockCppClassIR(properties=[])
        bp_vars = [
            MockBlueprintVariable(
                var_name="Mesh",
                var_type=MockPinType("object", "SkeletalMeshComponent"),
                default_value=None,
                is_component=True,
            )
        ]
        defaults = build_default_values(ir, blueprint_vars=bp_vars)
        assert len(defaults) == 0


# ============================================================================
# build_transform_assignments tests
# ============================================================================


class TestBuildTransformAssignments:
    def test_location_transform(self):
        ir = MockCppClassIR()
        components = [
            {
                "name": "FirstPersonCameraComponent",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {
                    "relative_location": {"X": 0.0, "Y": 15.0, "Z": 88.0},
                },
            }
        ]
        entries = build_transform_assignments(ir, components)
        assert len(entries) == 1
        assert entries[0].target == "FirstPersonCameraComponent"
        assert entries[0].cpp_type == "transform"
        assert entries[0].is_method_call is True
        assert entries[0].method_type == "transform"

    def test_rotation_transform(self):
        components = [
            {
                "name": "Cam",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {
                    "relative_rotation": {"Pitch": -10.0, "Yaw": 0.0, "Roll": 0.0},
                },
            }
        ]
        entries = build_transform_assignments(MockCppClassIR(), components)
        assert len(entries) == 1

    def test_both_location_and_rotation(self):
        components = [
            {
                "name": "Cam",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {
                    "relative_location": {"X": 0, "Y": 0, "Z": 88},
                    "relative_rotation": {"Pitch": 0, "Yaw": 0, "Roll": 0},
                },
            }
        ]
        entries = build_transform_assignments(MockCppClassIR(), components)
        assert len(entries) == 1
        # value should contain both location and rotation data
        assert "relative_location" in entries[0].value
        assert "relative_rotation" in entries[0].value

    def test_no_transforms_skipped(self):
        components = [
            {
                "name": "Mesh",
                "class": "SkeletalMeshComponent",
                "properties": {},
                "transforms": {},
            }
        ]
        entries = build_transform_assignments(MockCppClassIR(), components)
        assert len(entries) == 0

    def test_only_scale_no_location_rotation(self):
        """Only relative_scale3d (no loc/rot) should still produce entry."""
        components = [
            {
                "name": "Mesh",
                "class": "SkeletalMeshComponent",
                "properties": {},
                "transforms": {
                    "relative_scale3d": {"X": 1.0, "Y": 1.0, "Z": 1.0},
                },
            }
        ]
        entries = build_transform_assignments(MockCppClassIR(), components)
        assert len(entries) == 1

    def test_empty_components(self):
        entries = build_transform_assignments(MockCppClassIR(), [])
        assert entries == []

    def test_transform_value_preserves_objects(self):
        """Transform value should preserve the original dict, not convert to string."""
        transforms = {
            "relative_location": {"X": 0.0, "Y": 15.0, "Z": 88.0},
        }
        components = [
            {
                "name": "Cam",
                "class": "CameraComponent",
                "properties": {},
                "transforms": transforms,
            }
        ]
        entries = build_transform_assignments(MockCppClassIR(), components)
        assert entries[0].value is transforms  # same object reference


# ============================================================================
# _sanitize_value tests (T-059-02)
# ============================================================================


class TestSanitizeValue:
    def test_clean_value(self):
        assert _sanitize_value("100.0f", "float") == "100.0f"

    def test_remove_semicolon(self):
        result = _sanitize_value("value; rm -rf /", "FString")
        assert ";" not in result

    def test_remove_braces(self):
        result = _sanitize_value("{ malicious }", "FString")
        assert "{" not in result
        assert "}" not in result

    def test_remove_comment(self):
        result = _sanitize_value("value // inject", "FString")
        assert "//" not in result

    def test_safe_value_unchanged(self):
        assert _sanitize_value("true", "bool") == "true"
        assert _sanitize_value("42", "int32") == "42"


# ============================================================================
# _blueprint_var_type_to_cpp tests
# ============================================================================


class TestBlueprintVarTypeToCpp:
    def test_float(self):
        var = MockBlueprintVariable("X", var_type=MockPinType("FloatProperty"))
        assert _blueprint_var_type_to_cpp(var) == "float"

    def test_bool(self):
        var = MockBlueprintVariable("X", var_type=MockPinType("BoolProperty"))
        assert _blueprint_var_type_to_cpp(var) == "bool"

    def test_string(self):
        var = MockBlueprintVariable("X", var_type=MockPinType("StrProperty"))
        assert _blueprint_var_type_to_cpp(var) == "FString"

    def test_object_type(self):
        var = MockBlueprintVariable(
            "X", var_type=MockPinType("object", "UInputAction")
        )
        result = _blueprint_var_type_to_cpp(var)
        assert result == "UInputAction*"

    def test_struct_type(self):
        var = MockBlueprintVariable(
            "X", var_type=MockPinType("struct", "Vector")
        )
        result = _blueprint_var_type_to_cpp(var)
        assert "Vector" in result

    def test_fallback(self):
        var = MockBlueprintVariable("X", var_type=MockPinType("unknown"))
        result = _blueprint_var_type_to_cpp(var)
        assert result  # should not crash


# ============================================================================
# Integration test
# ============================================================================


class TestIntegration:
    def test_full_pipeline(self):
        """End-to-end: component_creations + assignments + defaults + transforms."""
        ir = MockCppClassIR(
            name="ABP_FirstPersonCharacter",
            properties=[
                # Components
                MockCppProperty("USkeletalMeshComponent*", "FirstPersonMesh", "component"),
                MockCppProperty("UCameraComponent*", "FirstPersonCameraComponent", "component"),
                # Variables
                MockCppProperty("float", "MoveSpeed", "variable", default_value=600.0),
                MockCppProperty("bool", "IsCrouching", "variable", default_value=False),
                # InputAction (should be skipped in creations, marked in defaults)
                MockCppProperty(
                    "UInputAction*", "IA_Jump", "variable",
                    default_value="/Game/Inputs/IA_Jump.IA_Jump",
                ),
            ],
        )
        components = [
            {
                "name": "FirstPersonCameraComponent",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {
                    "relative_location": {"X": 0, "Y": 15, "Z": 88},
                },
                "attach_parent": "FirstPersonMesh",
                "attach_socket_name": "head",
            },
        ]

        # Component creations
        creations = build_component_creations(ir)
        assert len(creations) == 2  # Mesh + Camera (not InputAction)

        # Component assignments
        assignments = build_component_assignments(components)
        assert len(assignments) == 1
        assert assignments[0].child_name == "FirstPersonCameraComponent"

        # Default values
        defaults = build_default_values(ir)
        # MoveSpeed, IsCrouching, IA_Jump (with needs_load_object)
        assert len(defaults) == 3

        # Transform assignments
        transforms = build_transform_assignments(ir, components)
        assert len(transforms) == 1
        assert transforms[0].method_type == "transform"
