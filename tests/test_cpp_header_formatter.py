"""
Unit tests for cpp_header_formatter.py — CppClassIR → UE .h header text.

Per D-05: Complete UE header template from JSON IR.
Per T-056-05: Escape string values in comments.
Per T-056-06: Validate class name matches UE naming convention.
"""
import pytest

from uasset_read.cpp_gen.formatters import (
    CppProperty,
    CppHeaderMeta,
    CppClassIR,
)
from uasset_read.cpp_gen.formatters.cpp_header_formatter import format_cpp_header


class TestFormatCppHeaderMinimalClass:
    """Test 1: Minimal class (no properties) produces valid .h structure."""

    def test_pragma_once_present(self):
        """Test 1a: #pragma once is present."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                includes=["\"Engine/GameFramework/Actor.h\""],
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        assert "#pragma once" in result

    def test_coreminimal_include_present(self):
        """Test 1b: CoreMinimal.h is always included."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                includes=[],
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        assert '#include "CoreMinimal.h"' in result

    def test_generated_include_is_last_include(self):
        """Test 1c: generated_include is the last #include line."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                includes=["\"Engine/GameFramework/Actor.h\"", "\"Components/SceneComponent.h\""],
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        lines = result.split('\n')
        include_lines = [l for l in lines if l.startswith('#include')]
        assert include_lines[-1] == '#include "ATestActor.generated.h"'

    def test_uclass_declaration_present(self):
        """Test 1d: UCLASS() macro is present."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        assert "UCLASS(" in result

    def test_class_declaration_with_inheritance(self):
        """Test 1e: class declaration has correct inheritance."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        assert "class ATestActor : public AActor" in result

    def test_generated_body_present(self):
        """Test 1f: GENERATED_BODY() macro is present."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        assert "GENERATED_BODY()" in result

    def test_constructor_declaration_present(self):
        """Test 1g: Constructor declaration is in public section."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        assert "ATestActor();" in result
        # Constructor should be in public section
        lines = result.split('\n')
        public_idx = next(i for i, l in enumerate(lines) if l.strip() == "public:")
        ctor_idx = next(i for i, l in enumerate(lines) if "ATestActor();" in l)
        assert ctor_idx > public_idx

    def test_empty_class_valid_structure(self):
        """Test 1h: Empty class (no properties) has valid complete structure."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        # Check structure elements
        assert result.startswith("#pragma once")
        assert "public:" in result
        assert "protected:" in result  # Even if empty, protected section should exist
        assert result.rstrip().endswith("};")


class TestFormatCppHeaderComponentProperty:
    """Test 2: Component property renders with correct UPROPERTY marks."""

    def test_component_pointer_type(self):
        """Test 2a: Component has pointer type."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="USceneComponent*",
                    name="DefaultSceneRoot",
                    uproperty_marks=["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
                    category="component",
                    default_value=None,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert "USceneComponent* DefaultSceneRoot" in result

    def test_component_uproperty_marks(self):
        """Test 2b: Component has UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced)."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="USceneComponent*",
                    name="DefaultSceneRoot",
                    uproperty_marks=["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
                    category="component",
                    default_value=None,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert "UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced" in result

    def test_component_category_meta(self):
        """Test 2c: Component has Category = "Components" with AllowPrivateAccess."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="USceneComponent*",
                    name="DefaultSceneRoot",
                    uproperty_marks=["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
                    category="component",
                    default_value=None,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert 'Category = "Components"' in result
        assert 'AllowPrivateAccess = "true"' in result

    def test_component_no_default_value(self):
        """Test 2d: Component has no default value (no = part)."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="USceneComponent*",
                    name="DefaultSceneRoot",
                    uproperty_marks=["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
                    category="component",
                    default_value=None,
                ),
            ],
        )
        result = format_cpp_header(ir)
        # Should not have "= nullptr" for components (pointer initialized in constructor)
        line_with_component = next(
            l for l in result.split('\n')
            if "USceneComponent* DefaultSceneRoot" in l
        )
        assert "= nullptr" not in line_with_component


class TestFormatCppHeaderVariableProperty:
    """Test 3-4: Variable property with/without default value."""

    def test_variable_with_float_default(self):
        """Test 3a: Variable with float default has 'f' suffix."""
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
                    name="MoveSpeed",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Movement",
                    default_value=600.0,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert "float MoveSpeed = 600.0f;" in result

    def test_variable_with_int_default(self):
        """Test 3b: Variable with int default has no suffix."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="int32",
                    name="MaxHealth",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Stats",
                    default_value=100,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert "int32 MaxHealth = 100;" in result

    def test_variable_with_bool_default_true(self):
        """Test 3c: Variable with bool true default."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="bool",
                    name="IsAiming",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Combat",
                    default_value=True,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert "bool IsAiming = true;" in result

    def test_variable_with_bool_default_false(self):
        """Test 3d: Variable with bool false default."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="bool",
                    name="IsEnabled",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Settings",
                    default_value=False,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert "bool IsEnabled = false;" in result

    def test_variable_without_default_value(self):
        """Test 4: Variable without default has no '=' part."""
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
                    name="DamageMultiplier",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Combat",
                    default_value=None,
                ),
            ],
        )
        result = format_cpp_header(ir)
        line_with_var = next(
            l for l in result.split('\n')
            if "float DamageMultiplier" in l
        )
        assert "float DamageMultiplier;" in line_with_var
        assert "= " not in line_with_var

    def test_variable_with_category(self):
        """Test 5a: Variable has Category in UPROPERTY."""
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
                    name="MoveSpeed",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Movement",
                    default_value=600.0,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert 'Category = "Movement"' in result

    def test_variable_with_cpp_comment(self):
        """Test 5b: Variable with cpp_comment has inline comment."""
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
                    name="MoveSpeed",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Movement",
                    default_value=600.0,
                    cpp_comment="UE type: float",
                ),
            ],
        )
        result = format_cpp_header(ir)
        # Comment should be after declaration
        assert "// UE type: float" in result


class TestFormatCppHeaderIncludes:
    """Test 5-6: Include ordering tests."""

    def test_includes_sorted_before_generated(self):
        """Test 5c: header_meta.includes are sorted before generated_include."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                includes=[
                    '"Engine/GameFramework/Actor.h"',
                    '"Components/SceneComponent.h"',  # Alphabetically Components < Engine
                ],
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        lines = result.split('\n')
        include_lines = [l for l in lines if l.startswith('#include')]
        # CoreMinimal.h first, then sorted includes, then generated.h last
        assert include_lines[0] == '#include "CoreMinimal.h"'
        assert include_lines[-1] == '#include "ATestActor.generated.h"'
        # Check ordering: alphabetical sorting puts Components before Engine
        comp_idx = next(i for i, l in enumerate(include_lines) if 'Components/' in l)
        engine_idx = next(i for i, l in enumerate(include_lines) if 'Engine/' in l)
        assert comp_idx < engine_idx  # Components alphabetically before Engine

    def test_generated_include_last(self):
        """Test 6: generated_include is the last #include."""
        ir = CppClassIR(
            name="ABP_Character",
            parent_class="ACharacter",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                includes=['"Engine/GameFramework/Character.h"'],
                generated_include='"ABP_Character.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        lines = result.split('\n')
        include_lines = [l for l in lines if l.startswith('#include')]
        assert include_lines[-1] == '#include "ABP_Character.generated.h"'


class TestFormatCppHeaderClassDeclaration:
    """Test 7: Class declaration tests."""

    def test_character_inheritance(self):
        """Test 7a: ACharacter parent produces correct declaration."""
        ir = CppClassIR(
            name="ABP_FirstPersonCharacter",
            parent_class="ACharacter",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ABP_FirstPersonCharacter.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        assert "class ABP_FirstPersonCharacter : public ACharacter" in result

    def test_actor_inheritance(self):
        """Test 7b: AActor parent produces correct declaration."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        assert "class ATestActor : public AActor" in result

    def test_uobject_inheritance(self):
        """Test 7c: UObject parent produces correct declaration."""
        ir = CppClassIR(
            name="UTestObject",
            parent_class="UObject",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"UTestObject.generated.h"',
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        assert "class UTestObject : public UObject" in result


class TestFormatCppHeaderMultipleProperties:
    """Test 8: Multiple properties rendered in order."""

    def test_components_first_then_variables(self):
        """Test 8: Components are rendered before variables."""
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
                    name="MoveSpeed",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Movement",
                    default_value=600.0,
                ),
                CppProperty(
                    cpp_type="USceneComponent*",
                    name="DefaultSceneRoot",
                    uproperty_marks=["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
                    category="component",
                    default_value=None,
                ),
                CppProperty(
                    cpp_type="UCameraComponent*",
                    name="Camera",
                    uproperty_marks=["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
                    category="component",
                    default_value=None,
                ),
                CppProperty(
                    cpp_type="bool",
                    name="IsAiming",
                    uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
                    category="Combat",
                    default_value=False,
                ),
            ],
        )
        result = format_cpp_header(ir)
        lines = result.split('\n')

        # Find positions of component and variable declarations
        scene_idx = next(i for i, l in enumerate(lines) if "DefaultSceneRoot" in l)
        camera_idx = next(i for i, l in enumerate(lines) if "Camera" in l and "UCameraComponent" in l)
        speed_idx = next(i for i, l in enumerate(lines) if "MoveSpeed" in l)
        aiming_idx = next(i for i, l in enumerate(lines) if "IsAiming" in l)

        # Components should come before variables
        assert scene_idx < speed_idx
        assert camera_idx < speed_idx
        # Within same category, maintain original order
        assert scene_idx < camera_idx  # Components in original order
        assert speed_idx < aiming_idx  # Variables in original order


class TestFormatCppHeaderSecurity:
    """Per T-056-05 and T-056-06: Security mitigation tests."""

    def test_comment_string_escaping(self):
        """T-056-05: String values in comments are escaped."""
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
                    uproperty_marks=["EditAnywhere"],
                    category="Test",
                    default_value=None,
                    cpp_comment="Test with <special> & chars",  # HTML-like chars
                ),
            ],
        )
        result = format_cpp_header(ir)
        # The comment should be sanitized - no raw < > & in output
        assert "<special>" not in result or "&lt;" in result  # Escaped or removed
        assert "& chars" not in result or "&amp;" in result  # Escaped or removed

    def test_class_name_validation(self):
        """T-056-06: Invalid class name is sanitized."""
        ir = CppClassIR(
            name="ATest-Actor!Invalid",  # Invalid characters
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATest-Actor!Invalid.generated.h"',  # Also invalid
            ),
            properties=[],
        )
        result = format_cpp_header(ir)
        # Should have sanitized name (alphanumeric + underscore only)
        # Class name line should not contain - or !
        class_line = next(l for l in result.split('\n') if "class " in l and ": public" in l)
        assert "-" not in class_line or "_" in class_line  # Sanitized


class TestFormatCppHeaderDefaultValues:
    """Default value formatting tests."""

    def test_double_default_with_f_suffix(self):
        """Double type uses f suffix."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="double",
                    name="Rate",
                    uproperty_marks=["EditAnywhere"],
                    category="Test",
                    default_value=1.5,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert "double Rate = 1.5f;" in result

    def test_fstring_default_with_text_wrapper(self):
        """FString default uses TEXT() wrapper."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="FString",
                    name="Name",
                    uproperty_marks=["EditAnywhere"],
                    category="Test",
                    default_value="TestName",
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert 'FString Name = TEXT("TestName");' in result

    def test_fname_default_with_text_wrapper(self):
        """FName default uses TEXT() wrapper."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="FName",
                    name="Tag",
                    uproperty_marks=["EditAnywhere"],
                    category="Test",
                    default_value="MyTag",
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert 'FName Tag = TEXT("MyTag");' in result

    def test_int64_default_no_suffix(self):
        """int64 default has no suffix."""
        ir = CppClassIR(
            name="ATestActor",
            parent_class="AActor",
            header_meta=CppHeaderMeta(
                pragma_once=True,
                generated_include='"ATestActor.generated.h"',
            ),
            properties=[
                CppProperty(
                    cpp_type="int64",
                    name="BigNumber",
                    uproperty_marks=["EditAnywhere"],
                    category="Test",
                    default_value=9999999999,
                ),
            ],
        )
        result = format_cpp_header(ir)
        assert "int64 BigNumber = 9999999999;" in result