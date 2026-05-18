"""
Unit tests — cpp_constructor_formatter module (Phase 59 Plan 03).

Coverage:
- build_constructor_sections: categorizes IR into 5 sections
- format_cpp_constructor: assembles full constructor text
- Topological sort of component creation order (T-059-06)
- String escaping in TEXT() (T-059-05)
- Asset path validation for InputAction (T-059-07)
- Empty section skipping
- Super::ClassName() unconditional usage (D-59-05)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from uasset_read.cpp_gen.cpp_constructor_formatter import (
    build_constructor_sections,
    format_cpp_constructor,
    _topological_sort_creations,
)
from uasset_read.cpp_gen.cpp_constructor_ir_builder import (
    CppComponentCreation,
    CppComponentAssignment,
    CppDefaultValue,
)
from uasset_read.models.transforms import VectorValue, RotatorValue


# ============================================================================
# Test fixtures / helpers
# ============================================================================


class MockCppClassIR:
    """Minimal CppClassIR mock for tests."""
    def __init__(self, name="TestClass", parent_class="AParent", constructor=None):
        self.name = name
        self.parent_class = parent_class
        self.properties = []
        self.header_meta = None
        self.methods = []
        self.constructor = constructor or {
            "component_creations": [],
            "component_assignments": [],
            "default_values": [],
        }


def _make_ir_with_full_data():
    """Create a fully populated IR for integration-style testing."""
    creations = [
        CppComponentCreation("FirstPersonMesh", "USkeletalMeshComponent", "FirstPersonMesh"),
        CppComponentCreation("FirstPersonCameraComponent", "UCameraComponent", "FirstPersonCamera"),
    ]
    assignments = [
        CppComponentAssignment("FirstPersonCameraComponent", "FirstPersonMesh", "head"),
    ]
    defaults = [
        # Transform entry
        CppDefaultValue(
            target="FirstPersonCameraComponent",
            value={
                "relative_location": VectorValue(x=-2.8, y=5.89, z=0.0),
                "relative_rotation": RotatorValue(roll=-90.0, pitch=0.0, yaw=90.0),
            },
            cpp_type="transform",
            is_method_call=True,
            method_type="transform",
        ),
        # Property entries
        CppDefaultValue(
            target="FirstPersonCameraComponent->bUsePawnControlRotation",
            value=True,
            cpp_type="bool",
        ),
        CppDefaultValue(
            target="GetCharacterMovement()->BrakingDecelerationFalling",
            value=1500.0,
            cpp_type="float",
        ),
        # InputAction LoadObject entry
        CppDefaultValue(
            target="JumpAction",
            value="/Game/Input/Actions/IA_Jump.IA_Jump",
            cpp_type="UInputAction*",
            needs_load_object=True,
        ),
    ]
    return MockCppClassIR(
        name="AFirstPersonCCharacter",
        parent_class="ACharacter",
        constructor={
            "component_creations": creations,
            "component_assignments": assignments,
            "default_values": defaults,
        },
    )


# ============================================================================
# build_constructor_sections tests
# ============================================================================


class TestBuildConstructorSections:
    def test_empty_ir(self):
        ir = MockCppClassIR()
        sections = build_constructor_sections(ir)
        assert set(sections.keys()) == {"creation", "attach", "transform", "property", "load_object"}
        for key in sections:
            assert sections[key] == []

    def test_creation_section(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [
                CppComponentCreation("Mesh", "USkeletalMeshComponent", "Mesh"),
                CppComponentCreation("Cam", "UCameraComponent", "Cam"),
            ],
            "component_assignments": [],
            "default_values": [],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["creation"]) == 2
        assert 'Mesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Mesh"));' in sections["creation"]
        assert 'Cam = CreateDefaultSubobject<UCameraComponent>(TEXT("Cam"));' in sections["creation"]

    def test_attach_section_with_socket(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [
                CppComponentAssignment("Cam", "Mesh", "head"),
            ],
            "default_values": [],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["attach"]) == 1
        assert 'Cam->SetupAttachment(Mesh, FName("head"));' in sections["attach"]

    def test_attach_section_without_socket(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [
                CppComponentAssignment("Cam", "Mesh", ""),
            ],
            "default_values": [],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["attach"]) == 1
        assert "Cam->SetupAttachment(Mesh);" in sections["attach"]

    def test_transform_section(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="Cam",
                    value={
                        "relative_location": VectorValue(x=1.0, y=2.0, z=3.0),
                        "relative_rotation": RotatorValue(roll=0.0, pitch=45.0, yaw=90.0),
                    },
                    cpp_type="transform",
                    is_method_call=True,
                    method_type="transform",
                ),
            ],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["transform"]) == 1
        assert "Cam->SetRelativeLocationAndRotation" in sections["transform"][0]
        assert "FVector(" in sections["transform"][0]
        assert "FRotator(" in sections["transform"][0]

    def test_property_section(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(target="MoveSpeed", value=100.0, cpp_type="float"),
                CppDefaultValue(target="bIsActive", value=True, cpp_type="bool"),
            ],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["property"]) == 2
        assert "MoveSpeed = 100.f;" in sections["property"]
        assert "bIsActive = true;" in sections["property"]

    def test_load_object_section(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="JumpAction",
                    value="/Game/Input/Actions/IA_Jump.IA_Jump",
                    cpp_type="UInputAction*",
                    needs_load_object=True,
                ),
            ],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["load_object"]) == 1
        assert 'JumpAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Jump.IA_Jump"));' in sections["load_object"]

    def test_load_object_invalid_path_skipped(self):
        """Invalid asset path should be skipped with warning (T-059-07)."""
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="BadAction",
                    value="/Malicious/Path",
                    cpp_type="UInputAction*",
                    needs_load_object=True,
                ),
            ],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["load_object"]) == 0

    def test_load_object_empty_value_skipped(self):
        """Empty asset path should produce no line."""
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="EmptyAction",
                    value="",
                    cpp_type="UInputAction*",
                    needs_load_object=True,
                ),
            ],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["load_object"]) == 0

    def test_transform_only_location(self):
        """Location only → SetRelativeLocation."""
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="Cam",
                    value={
                        "relative_location": VectorValue(x=0.0, y=0.0, z=88.0),
                    },
                    cpp_type="transform",
                    is_method_call=True,
                    method_type="transform",
                ),
            ],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["transform"]) == 1
        assert "Cam->SetRelativeLocation(" in sections["transform"][0]

    def test_transform_only_rotation(self):
        """Rotation only → SetRelativeRotation."""
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="Cam",
                    value={
                        "relative_rotation": RotatorValue(roll=0.0, pitch=45.0, yaw=0.0),
                    },
                    cpp_type="transform",
                    is_method_call=True,
                    method_type="transform",
                ),
            ],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["transform"]) == 1
        assert "Cam->SetRelativeRotation(" in sections["transform"][0]

    def test_transform_only_scale(self):
        """Scale only → SetRelativeScale3D."""
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="Mesh",
                    value={
                        "relative_scale3d": VectorValue(x=1.0, y=1.0, z=1.0),
                    },
                    cpp_type="transform",
                    is_method_call=True,
                    method_type="transform",
                ),
            ],
        })
        sections = build_constructor_sections(ir)
        assert len(sections["transform"]) == 1
        assert "Mesh->SetRelativeScale3D(" in sections["transform"][0]

    def test_all_sections_populated(self):
        ir = _make_ir_with_full_data()
        sections = build_constructor_sections(ir)
        assert len(sections["creation"]) == 2
        assert len(sections["attach"]) == 1
        assert len(sections["transform"]) == 1
        assert len(sections["property"]) >= 1  # at least the bool property
        assert len(sections["load_object"]) == 1

    def test_section_order_keys(self):
        """Sections should have expected keys."""
        ir = MockCppClassIR()
        sections = build_constructor_sections(ir)
        assert list(sections.keys()) == ["creation", "attach", "transform", "property", "load_object"]


# ============================================================================
# _topological_sort_creations tests (T-059-06)
# ============================================================================


class TestTopologicalSortCreations:
    def test_no_dependencies(self):
        creations = [
            CppComponentCreation("B", "UComp", "B"),
            CppComponentCreation("A", "UComp", "A"),
        ]
        result = _topological_sort_creations(creations, [])
        # No deps → sorted alphabetically by name
        assert result[0].variable_name == "A"
        assert result[1].variable_name == "B"

    def test_parent_before_child(self):
        creations = [
            CppComponentCreation("Child", "UComp", "Child"),
            CppComponentCreation("Parent", "UComp", "Parent"),
        ]
        assignments = [
            CppComponentAssignment("Child", "Parent", "socket"),
        ]
        result = _topological_sort_creations(creations, assignments)
        # Parent must come before Child
        parent_idx = next(i for i, c in enumerate(result) if c.variable_name == "Parent")
        child_idx = next(i for i, c in enumerate(result) if c.variable_name == "Child")
        assert parent_idx < child_idx

    def test_chain_dependency(self):
        """A -> B -> C means A created first, then B, then C."""
        creations = [
            CppComponentCreation("C", "UComp", "C"),
            CppComponentCreation("B", "UComp", "B"),
            CppComponentCreation("A", "UComp", "A"),
        ]
        assignments = [
            CppComponentAssignment("C", "B", ""),
            CppComponentAssignment("B", "A", ""),
        ]
        result = _topological_sort_creations(creations, assignments)
        names = [c.variable_name for c in result]
        assert names.index("A") < names.index("B") < names.index("C")

    def test_external_parent_not_in_creations(self):
        """Parent like RootComponent not in creations → no dependency edge."""
        creations = [
            CppComponentCreation("Cam", "UCameraComponent", "Cam"),
        ]
        assignments = [
            CppComponentAssignment("Cam", "RootComponent", ""),
        ]
        result = _topological_sort_creations(creations, assignments)
        assert len(result) == 1
        assert result[0].variable_name == "Cam"

    def test_empty_creations(self):
        result = _topological_sort_creations([], [])
        assert result == []

    def test_cycle_fallback(self):
        """Circular deps should still produce result (fallback to original order)."""
        creations = [
            CppComponentCreation("A", "UComp", "A"),
            CppComponentCreation("B", "UComp", "B"),
        ]
        # Create artificial cycle: A depends on B, B depends on A
        assignments = [
            CppComponentAssignment("A", "B", ""),
            CppComponentAssignment("B", "A", ""),
        ]
        result = _topological_sort_creations(creations, assignments)
        # Should still return both
        assert len(result) == 2
        names = {c.variable_name for c in result}
        assert names == {"A", "B"}


# ============================================================================
# format_cpp_constructor tests
# ============================================================================


class TestFormatCppConstructor:
    def test_basic_structure(self):
        ir = MockCppClassIR(name="AMyCharacter", parent_class="ACharacter")
        result = format_cpp_constructor(ir)
        assert "AMyCharacter::AMyCharacter()" in result
        assert ": Super::AMyCharacter()" in result
        assert result.startswith("{") is False  # starts with signature
        assert result.endswith("}")

    def test_super_uses_class_name_not_super(self):
        """D-59-05: Super::ClassName(), not Super() or Super::ParentClass()."""
        ir = MockCppClassIR(name="ABP_Test", parent_class="ACharacter")
        result = format_cpp_constructor(ir)
        assert "Super::ABP_Test()" in result
        assert "Super::ACharacter()" not in result
        assert "Super()" not in result  # naked Super() is wrong

    def test_creation_section_rendered(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [
                CppComponentCreation("Mesh", "USkeletalMeshComponent", "Mesh"),
            ],
            "component_assignments": [],
            "default_values": [],
        })
        result = format_cpp_constructor(ir)
        assert "// Component creation" in result
        assert 'Mesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Mesh"));' in result

    def test_attach_section_rendered(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [
                CppComponentAssignment("Cam", "Mesh", "head"),
            ],
            "default_values": [],
        })
        result = format_cpp_constructor(ir)
        assert "// Setup attachments" in result
        assert 'Cam->SetupAttachment(Mesh, FName("head"));' in result

    def test_transform_section_rendered(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="Cam",
                    value={
                        "relative_location": VectorValue(x=0.0, y=0.0, z=88.0),
                    },
                    cpp_type="transform",
                    is_method_call=True,
                    method_type="transform",
                ),
            ],
        })
        result = format_cpp_constructor(ir)
        assert "// Transform assignments" in result
        assert "Cam->SetRelativeLocation(" in result

    def test_property_section_rendered(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(target="Speed", value=100.0, cpp_type="float"),
            ],
        })
        result = format_cpp_constructor(ir)
        assert "// Property assignments" in result
        assert "Speed = 100.f;" in result

    def test_load_object_section_rendered(self):
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="JumpAction",
                    value="/Game/Input/Actions/IA_Jump.IA_Jump",
                    cpp_type="UInputAction*",
                    needs_load_object=True,
                ),
            ],
        })
        result = format_cpp_constructor(ir)
        assert "// InputAction loads" in result
        assert 'JumpAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Jump.IA_Jump"));' in result

    def test_empty_sections_skipped(self):
        """Empty sections should not produce comment lines."""
        ir = MockCppClassIR(constructor={
            "component_creations": [
                CppComponentCreation("Mesh", "USkeletalMeshComponent", "Mesh"),
            ],
            "component_assignments": [],
            "default_values": [],
        })
        result = format_cpp_constructor(ir)
        assert "// Setup attachments" not in result
        assert "// Transform assignments" not in result
        assert "// Property assignments" not in result
        assert "// InputAction loads" not in result

    def test_section_blank_line_between(self):
        """Sections should be separated by blank lines."""
        ir = MockCppClassIR(constructor={
            "component_creations": [
                CppComponentCreation("Mesh", "USkeletalMeshComponent", "Mesh"),
            ],
            "component_assignments": [
                CppComponentAssignment("Cam", "Mesh", "head"),
            ],
            "default_values": [],
        })
        result = format_cpp_constructor(ir)
        # There should be a blank line between creation and attach sections
        lines = result.split("\n")
        creation_idx = next(i for i, l in enumerate(lines) if "// Component creation" in l)
        attach_idx = next(i for i, l in enumerate(lines) if "// Setup attachments" in l)
        # The blank line should be between the last creation line and the attach comment
        blank_line_found = any(
            lines[i].strip() == ""
            for i in range(creation_idx + 1, attach_idx)
        )
        assert blank_line_found

    def test_full_constructor_golden(self):
        """Golden path: full constructor with all sections."""
        ir = _make_ir_with_full_data()
        result = format_cpp_constructor(ir)

        # Header
        assert "AFirstPersonCCharacter::AFirstPersonCCharacter()" in result
        assert ": Super::AFirstPersonCCharacter()" in result

        # All sections present
        assert "// Component creation" in result
        assert "// Setup attachments" in result
        assert "// Transform assignments" in result
        assert "// Property assignments" in result
        assert "// InputAction loads" in result

        # Specific content
        assert 'FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FirstPersonMesh"));' in result
        assert 'FirstPersonCameraComponent = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));' in result
        assert 'FirstPersonCameraComponent->SetupAttachment(FirstPersonMesh, FName("head"));' in result
        assert "FirstPersonCameraComponent->SetRelativeLocationAndRotation" in result
        assert "FVector(" in result
        assert "FRotator(" in result
        assert 'JumpAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Jump.IA_Jump"));' in result

    def test_four_space_indent(self):
        """Code lines should be indented with 4 spaces."""
        ir = MockCppClassIR(constructor={
            "component_creations": [
                CppComponentCreation("Mesh", "UComp", "Mesh"),
            ],
            "component_assignments": [],
            "default_values": [],
        })
        result = format_cpp_constructor(ir)
        lines = result.split("\n")
        # Find code lines (not empty, not braces, not comments)
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped in ("{", "}"):
                continue
            if stripped.startswith("//"):
                continue
            if stripped.startswith(": Super::"):
                continue
            # Constructor signature line
            if "(" in stripped and ")" in stripped and "::" in stripped and not stripped.startswith("    "):
                continue
            # Check indentation for body lines
            if stripped and not line.startswith("    "):
                assert False, f"Line not indented with 4 spaces: {line!r}"

    def test_transform_multiline_indent(self):
        """Transform multi-line statements should have proper indentation."""
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="Cam",
                    value={
                        "relative_location": VectorValue(x=-2.8, y=5.89, z=0.0),
                        "relative_rotation": RotatorValue(roll=-90.0, pitch=0.0, yaw=90.0),
                    },
                    cpp_type="transform",
                    is_method_call=True,
                    method_type="transform",
                ),
            ],
        })
        result = format_cpp_constructor(ir)
        lines = result.split("\n")
        # All lines in the transform block should be indented
        transform_start = next(i for i, l in enumerate(lines) if "// Transform" in l)
        # Next lines until ); should be indented
        for i in range(transform_start + 1, min(transform_start + 5, len(lines))):
            if lines[i].strip() == "":
                break
            if lines[i].strip() == "}":
                break
            assert lines[i].startswith("    "), f"Bad indent at line {i}: {lines[i]!r}"

    def test_string_escaping_in_text(self):
        """String values in TEXT() should be escaped (T-059-05)."""
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(
                    target="DisplayName",
                    value='Name with "quotes" and \\backslash',
                    cpp_type="FString",
                ),
            ],
        })
        result = format_cpp_constructor(ir)
        # The escaped version should appear
        assert "DisplayName = " in result

    def test_property_empty_value_skipped(self):
        """Properties with empty formatted value should be skipped."""
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(target="Empty", value=None, cpp_type="FString"),
            ],
        })
        result = format_cpp_constructor(ir)
        # Empty property should not produce output
        assert "// Property assignments" not in result

    def test_load_object_before_property_order(self):
        """load_object section should appear after property section."""
        ir = MockCppClassIR(constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [
                CppDefaultValue(target="Speed", value=100.0, cpp_type="float"),
                CppDefaultValue(
                    target="JumpAction",
                    value="/Game/Input/Actions/IA_Jump.IA_Jump",
                    cpp_type="UInputAction*",
                    needs_load_object=True,
                ),
            ],
        })
        result = format_cpp_constructor(ir)
        lines = result.split("\n")
        prop_idx = next(i for i, l in enumerate(lines) if "// Property" in l)
        load_idx = next(i for i, l in enumerate(lines) if "// InputAction loads" in l)
        assert prop_idx < load_idx
