"""C++ 默认值格式化器单元测试。

Phase 59 Plan 02: 验证 format_cpp_default_value, format_cpp_transform,
format_cpp_component_init, format_cpp_input_action_load 函数正确性。
"""
from __future__ import annotations

import pytest

from uasset_read.cpp_gen.cpp_default_value_formatter import (
    _escape_cpp_string,
    _validate_no_cpp_syntax,
    _format_float_value,
    _format_fvector,
    _format_frotator,
    format_cpp_default_value,
    format_cpp_transform,
    format_cpp_component_init,
    format_cpp_input_action_load,
)
from uasset_read.models.transforms import RotatorValue, ScaleValue, VectorValue


# ============================================================================
# 辅助函数测试
# ============================================================================

class TestEscapeCppString:
    def test_no_special_chars(self):
        assert _escape_cpp_string("hello") == "hello"

    def test_escape_double_quote(self):
        assert _escape_cpp_string('say "hi"') == r'say \"hi\"'

    def test_escape_backslash(self):
        assert _escape_cpp_string(r"path\to") == r"path\\to"

    def test_escape_newline(self):
        assert _escape_cpp_string("hello\nworld") == r"hello\nworld"

    def test_escape_tab(self):
        assert _escape_cpp_string("hello\tworld") == r"hello\tworld"

    def test_combined_escapes(self):
        result = _escape_cpp_string('path\n"to"\tfile')
        assert r"path\n\"to\"\tfile" == result


class TestValidateNoCppSyntax:
    def test_safe_string(self):
        assert _validate_no_cpp_syntax("hello") == "hello"

    def test_rejects_semicolon(self):
        with pytest.raises(ValueError, match=";"):
            _validate_no_cpp_syntax("value; injected")

    def test_rejects_open_brace(self):
        with pytest.raises(ValueError, match=r"\{"):
            _validate_no_cpp_syntax("value{injected}")

    def test_rejects_close_brace(self):
        with pytest.raises(ValueError, match=r"\}"):
            _validate_no_cpp_syntax("value}injected")

    def test_rejects_comment(self):
        with pytest.raises(ValueError, match="//"):
            _validate_no_cpp_syntax("value // injected")


class TestFormatFloatValue:
    def test_integer_value(self):
        assert _format_float_value(55.0) == "55.f"

    def test_decimal_value(self):
        assert _format_float_value(400.12) == "400.12f"

    def test_negative_value(self):
        assert _format_float_value(-2.8) == "-2.8f"

    def test_zero(self):
        assert _format_float_value(0.0) == "0.f"


class TestFormatFVector:
    def test_basic(self):
        result = _format_fvector(1.0, 2.0, 3.0)
        assert result == "FVector(1.f, 2.f, 3.f)"

    def test_negative(self):
        result = _format_fvector(-2.8, 5.89, 0.0)
        assert result == "FVector(-2.8f, 5.89f, 0.f)"


class TestFormatFRotator:
    def test_basic(self):
        result = _format_frotator(0.0, 90.0, -90.0)
        assert result == "FRotator(0.f, 90.f, -90.f)"

    def test_parameter_order(self):
        """FRotator 构造函数顺序: pitch, yaw, roll"""
        result = _format_frotator(45.0, 180.0, 0.0)
        assert result == "FRotator(45.f, 180.f, 0.f)"


# ============================================================================
# format_cpp_default_value 测试
# ============================================================================

class TestFormatCppDefaultValue:
    def test_float_integer_value(self):
        assert format_cpp_default_value(55, "float") == "55.f"

    def test_float_decimal_value(self):
        assert format_cpp_default_value(400.12, "float") == "400.12f"

    def test_float_zero(self):
        assert format_cpp_default_value(0.0, "float") == "0.f"

    def test_double_no_suffix(self):
        assert format_cpp_default_value(96.0, "double") == "96.0"

    def test_bool_true(self):
        assert format_cpp_default_value(True, "bool") == "true"

    def test_bool_false(self):
        assert format_cpp_default_value(False, "bool") == "false"

    def test_bool_int_truthy(self):
        assert format_cpp_default_value(1, "bool") == "true"

    def test_bool_int_falsy(self):
        assert format_cpp_default_value(0, "bool") == "false"

    def test_bool_string_true(self):
        assert format_cpp_default_value("true", "bool") == "true"

    def test_bool_string_false(self):
        assert format_cpp_default_value("false", "bool") == "false"

    def test_int32(self):
        assert format_cpp_default_value(1500, "int32") == "1500"

    def test_int(self):
        assert format_cpp_default_value(42, "int") == "42"

    def test_int64(self):
        assert format_cpp_default_value(9223372036854775807, "int64") == "9223372036854775807"

    def test_uint8(self):
        assert format_cpp_default_value(255, "uint8") == "255"

    def test_byte(self):
        assert format_cpp_default_value(128, "byte") == "128"

    def test_fstring(self):
        assert format_cpp_default_value("value", "FString") == 'TEXT("value")'

    def test_fname(self):
        assert format_cpp_default_value("head", "FName") == 'TEXT("head")'

    def test_fstring_with_quotes(self):
        result = format_cpp_default_value('say "hi"', "FString")
        assert result == r'TEXT("say \"hi\"")'

    def test_fstring_rejects_semicolon(self):
        with pytest.raises(ValueError, match=";"):
            format_cpp_default_value("bad;value", "FString")

    def test_fstring_rejects_braces(self):
        with pytest.raises(ValueError):
            format_cpp_default_value("bad{value", "FString")

    def test_ftext(self):
        assert format_cpp_default_value("hello", "FText") == 'FText::FromString("hello")'

    def test_ftext_with_quotes(self):
        result = format_cpp_default_value('say "hi"', "FText")
        assert result == r'FText::FromString("say \"hi\"")'

    def test_enum(self):
        result = format_cpp_default_value(
            "EFirstPersonPrimitiveType::FirstPerson", "EFirstPersonPrimitiveType"
        )
        assert result == "EFirstPersonPrimitiveType::FirstPerson"

    def test_none_returns_empty(self):
        assert format_cpp_default_value(None, "float") == ""

    def test_unknown_type(self):
        assert format_cpp_default_value(42, "UnknownType") == "42"


# ============================================================================
# format_cpp_transform 测试
# ============================================================================

class TestFormatCppTransform:
    def test_location_and_rotation(self):
        loc = VectorValue(x=-2.8, y=5.89, z=0.0)
        rot = RotatorValue(roll=-90.0, pitch=0.0, yaw=90.0)
        transforms = {"relative_location": loc, "relative_rotation": rot}
        result = format_cpp_transform(transforms, "FirstPersonCameraComponent")

        assert len(result) == 1
        assert "SetRelativeLocationAndRotation" in result[0]
        assert "FVector(-2.8f, 5.89f, 0.f)" in result[0]
        assert "FRotator(0.f, 90.f, -90.f)" in result[0]

    def test_location_only(self):
        loc = VectorValue(x=1.0, y=2.0, z=3.0)
        transforms = {"relative_location": loc}
        result = format_cpp_transform(transforms, "MyComponent")

        assert len(result) == 1
        assert "SetRelativeLocation" in result[0]
        assert "SetRelativeRotation" not in result[0]
        assert "FVector(1.f, 2.f, 3.f)" in result[0]

    def test_rotation_only(self):
        rot = RotatorValue(roll=0.0, pitch=45.0, yaw=90.0)
        transforms = {"relative_rotation": rot}
        result = format_cpp_transform(transforms, "MyComponent")

        assert len(result) == 1
        assert "SetRelativeRotation" in result[0]
        assert "SetRelativeLocation" not in result[0]
        assert "FRotator(45.f, 90.f, 0.f)" in result[0]

    def test_scale_only(self):
        scale = ScaleValue(x=1.5, y=1.5, z=1.5)
        transforms = {"relative_scale": scale}
        result = format_cpp_transform(transforms, "MyComponent")

        assert len(result) == 1
        assert "SetRelativeScale3D" in result[0]
        assert "FVector(1.5f, 1.5f, 1.5f)" in result[0]

    def test_location_rotation_scale(self):
        loc = VectorValue(x=0.0, y=0.0, z=0.0)
        rot = RotatorValue(roll=0.0, pitch=0.0, yaw=0.0)
        scale = ScaleValue(x=2.0, y=2.0, z=2.0)
        transforms = {
            "relative_location": loc,
            "relative_rotation": rot,
            "relative_scale": scale,
        }
        result = format_cpp_transform(transforms, "MyComponent")

        # location+rotation combined, scale separate
        assert len(result) == 2
        assert "SetRelativeLocationAndRotation" in result[0]
        assert "SetRelativeScale3D" in result[1]

    def test_empty_transforms(self):
        result = format_cpp_transform({}, "MyComponent")
        assert result == []

    def test_none_transforms(self):
        result = format_cpp_transform(None, "MyComponent")
        assert result == []


# ============================================================================
# format_cpp_component_init 测试
# ============================================================================

class TestFormatCppComponentInit:
    def test_basic_creation_only(self):
        result = format_cpp_component_init(
            "FirstPersonMesh", "USkeletalMeshComponent"
        )
        assert len(result) == 1
        assert 'FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FirstPersonMesh"));' in result[0]

    def test_with_transforms(self):
        loc = VectorValue(x=-2.8, y=5.89, z=0.0)
        rot = RotatorValue(roll=-90.0, pitch=0.0, yaw=90.0)
        transforms = {"relative_location": loc, "relative_rotation": rot}
        result = format_cpp_component_init(
            "FirstPersonCameraComponent", "UCameraComponent", transforms=transforms
        )
        assert len(result) == 2
        assert "CreateDefaultSubobject" in result[0]
        assert "SetRelativeLocationAndRotation" in result[1]

    def test_with_properties(self):
        properties = {
            "bVisible": ("bool", True),
            "RenderPriority": ("int32", 100),
        }
        result = format_cpp_component_init(
            "MyComponent", "UActorComponent", properties=properties
        )
        assert len(result) == 3
        assert "MyComponent->bVisible = true;" in result[1]
        assert "MyComponent->RenderPriority = 100;" in result[2]

    def test_full_initialization(self):
        """完整组件初始化：创建 + transform + 属性"""
        loc = VectorValue(x=0.0, y=0.0, z=0.0)
        rot = RotatorValue(roll=0.0, pitch=0.0, yaw=0.0)
        transforms = {"relative_location": loc, "relative_rotation": rot}
        properties = {"bUsePawnControlRotation": ("bool", True)}
        result = format_cpp_component_init(
            "FirstPersonCameraComponent",
            "UCameraComponent",
            transforms=transforms,
            properties=properties,
        )
        assert len(result) == 3
        assert "CreateDefaultSubobject" in result[0]
        assert "SetRelativeLocationAndRotation" in result[1]
        assert "bUsePawnControlRotation = true" in result[2]


# ============================================================================
# format_cpp_input_action_load 测试
# ============================================================================

class TestFormatCppInputActionLoad:
    def test_valid_path(self):
        result = format_cpp_input_action_load(
            "JumpAction", "/Game/Input/Actions/IA_Jump.IA_Jump"
        )
        assert (
            result
            == 'JumpAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Jump.IA_Jump"));'
        )

    def test_empty_path(self):
        result = format_cpp_input_action_load("JumpAction", "")
        assert result == ""

    def test_none_path(self):
        result = format_cpp_input_action_load("JumpAction", None)
        assert result == ""

    def test_invalid_path_no_game(self):
        with pytest.raises(ValueError, match="/Game/"):
            format_cpp_input_action_load("JumpAction", "/Engine/BasicShapes/Cube")

    def test_invalid_path_relative(self):
        with pytest.raises(ValueError, match="/Game/"):
            format_cpp_input_action_load("JumpAction", "SomeAction.SomeAction")

    def test_escaped_quotes_in_path(self):
        result = format_cpp_input_action_load(
            "MyAction", '/Game/Input/"Quoted".IA_Test'
        )
        assert r"\"Quoted\"" in result
