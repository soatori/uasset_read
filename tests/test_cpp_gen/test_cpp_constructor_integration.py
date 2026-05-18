"""
Golden-path integration tests — cpp_constructor_formatter (Phase 59 Plan 03).

Coverage:
- Full pipeline: extract_cpp_class_skeleton -> build IR -> format_cpp_constructor
- BP_FirstPersonCharacter golden case
- Golden-path constructor text matches expected output
"""
from __future__ import annotations

import pytest

from uasset_read.cpp_gen.cpp_constructor_formatter import (
    build_constructor_sections,
    format_cpp_constructor,
)
from uasset_read.cpp_gen.cpp_constructor_ir_builder import (
    CppComponentCreation,
    CppComponentAssignment,
    CppDefaultValue,
)
from uasset_read.cpp_gen.extract_cpp_skeleton import (
    extract_cpp_class_skeleton,
    extract_cpp_constructor,
)


# ============================================================================
# Mock LinkerParseResult for golden-path testing
# ============================================================================


class MockPinType:
    """Minimal FEdGraphPinType mock."""
    def __init__(self, category="", subcategory=""):
        self.pin_category = category
        self.pin_subcategory = subcategory
        self.pin_subcategory_object = None
        self.container_type = 0
        self.is_reference = False
        self.is_const = False


class MockBlueprintVariable:
    """Minimal BlueprintVariable mock."""
    def __init__(
        self,
        var_name: str,
        var_type=None,
        default_value=None,
        is_component: bool = False,
        property_flags: int = 0,
    ):
        self.var_name = var_name
        self.var_type = var_type or MockPinType("float")
        self.default_value = default_value
        self.is_component = is_component
        self.property_flags = property_flags


class MockBlueprintMetadata:
    """Minimal BlueprintMetadata mock."""
    def __init__(
        self,
        parent_class: str = "/Script/Engine.Character",
        variables: list = None,
        is_blueprint: bool = True,
    ):
        self.parent_class = parent_class
        self.variables = variables or []
        self.is_blueprint = is_blueprint


class MockSummary:
    """Minimal summary mock."""
    def __init__(self, package_name: str = "BP_FirstPersonCharacter"):
        self.package_name = package_name


class MockLinker:
    """Minimal PackageLinker mock."""
    pass


class MockLinkerParseResult:
    """Minimal LinkerParseResult mock for golden-path testing."""
    def __init__(
        self,
        class_name: str = "BP_FirstPersonCharacter",
        components: list = None,
        blueprint_vars: list = None,
    ):
        self.summary = MockSummary(class_name)
        self.name_map = [class_name]
        self.components = components or []
        self.blueprint = MockBlueprintMetadata(
            parent_class="/Script/Engine.Character",
            variables=blueprint_vars or [],
            is_blueprint=True,
        )
        self.linker = MockLinker()


# ============================================================================
# Golden-path: extract_cpp_class_skeleton integration
# ============================================================================


class TestExtractCppClassSkeletonIntegration:
    def test_constructor_populated_after_extraction(self):
        """extract_cpp_class_skeleton should populate ir.constructor."""
        components = [
            {
                "name": "FirstPersonMesh",
                "class": "SkeletalMeshComponent",
                "properties": {},
                "transforms": {},
            },
            {
                "name": "FirstPersonCameraComponent",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {
                    "relative_location": {"X": -2.8, "Y": 5.89, "Z": 0.0},
                    "relative_rotation": {"Pitch": 0.0, "Yaw": 90.0, "Roll": -90.0},
                },
                "attach_parent": "FirstPersonMesh",
                "attach_socket_name": "head",
            },
        ]
        blueprint_vars = [
            MockBlueprintVariable(
                var_name="JumpAction",
                var_type=MockPinType("object", "InputAction"),
                default_value="/Game/Input/Actions/IA_Jump.IA_Jump",
            ),
            MockBlueprintVariable(
                var_name="MoveSpeed",
                var_type=MockPinType("FloatProperty"),
                default_value=600.0,
            ),
        ]

        result = MockLinkerParseResult(
            components=components,
            blueprint_vars=blueprint_vars,
        )
        result.blueprint.variables = blueprint_vars

        ir = extract_cpp_class_skeleton(result)

        # Verify constructor sections are populated
        assert len(ir.constructor["component_creations"]) >= 1
        assert len(ir.constructor["component_assignments"]) >= 1
        assert len(ir.constructor["default_values"]) >= 1

        # Verify transform entries exist
        transform_entries = [
            e for e in ir.constructor["default_values"]
            if e.is_method_call and e.method_type == "transform"
        ]
        assert len(transform_entries) >= 1

        # Verify constructor_text is generated
        assert "constructor_text" in ir.constructor
        assert ir.constructor["constructor_text"]  # non-empty

    def test_constructor_text_contains_super_call(self):
        """Generated constructor text must contain Super::ClassName()."""
        components = [
            {
                "name": "Mesh",
                "class": "SkeletalMeshComponent",
                "properties": {},
                "transforms": {},
            },
        ]
        result = MockLinkerParseResult(components=components)
        ir = extract_cpp_class_skeleton(result)
        text = ir.constructor["constructor_text"]
        assert "Super::" in text

    def test_constructor_text_contains_component_creation(self):
        """Generated constructor must contain CreateDefaultSubobject calls."""
        components = [
            {
                "name": "FirstPersonMesh",
                "class": "SkeletalMeshComponent",
                "properties": {},
                "transforms": {},
            },
        ]
        result = MockLinkerParseResult(components=components)
        ir = extract_cpp_class_skeleton(result)
        text = ir.constructor["constructor_text"]
        assert "CreateDefaultSubobject" in text
        assert "FirstPersonMesh" in text

    def test_constructor_text_contains_setup_attachment(self):
        """Generated constructor must contain SetupAttachment."""
        components = [
            {
                "name": "Cam",
                "class": "CameraComponent",
                "properties": {},
                "transforms": {},
                "attach_parent": "Mesh",
                "attach_socket_name": "head",
            },
            {
                "name": "Mesh",
                "class": "SkeletalMeshComponent",
                "properties": {},
                "transforms": {},
            },
        ]
        result = MockLinkerParseResult(components=components)
        ir = extract_cpp_class_skeleton(result)
        text = ir.constructor["constructor_text"]
        assert "SetupAttachment" in text


# ============================================================================
# Golden-path: format_cpp_constructor with BP_FirstPersonCharacter data
# ============================================================================


class TestFormatCppConstructorGolden:
    def test_bp_first_person_character_full_constructor(self):
        """Golden case: BP_FirstPersonCharacter full constructor output."""
        from uasset_read.models.transforms import VectorValue, RotatorValue

        ir = _make_bp_first_person_ir()
        text = format_cpp_constructor(ir)

        # Structure checks
        assert "ABP_FirstPersonCharacter::ABP_FirstPersonCharacter()" in text
        assert ": Super::ABP_FirstPersonCharacter()" in text
        assert "{" in text
        assert "}" in text

        # Section presence
        assert "// Component creation" in text
        assert "// Setup attachments" in text
        assert "// Transform assignments" in text
        assert "// Property assignments" in text
        assert "// InputAction loads" in text

        # Component creation order (parent before child)
        creation_section_start = text.index("// Component creation")
        attach_section_start = text.index("// Setup attachments")
        creation_block = text[creation_section_start:attach_section_start]
        mesh_idx = creation_block.index("FirstPersonMesh")
        camera_idx = creation_block.index("FirstPersonCameraComponent")
        assert mesh_idx < camera_idx, "Parent component should be created before child"

        # Attach with socket
        assert 'FirstPersonCameraComponent->SetupAttachment(FirstPersonMesh, FName("head"))' in text

        # Transform assignment
        assert "FirstPersonCameraComponent->SetRelativeLocationAndRotation" in text
        assert "FVector(" in text
        assert "FRotator(" in text

        # Property assignments
        assert "FirstPersonCameraComponent->bUsePawnControlRotation = true;" in text

        # InputAction load
        assert 'JumpAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Jump.IA_Jump"))' in text

    def test_extract_cpp_constructor_function(self):
        """extract_cpp_constructor should be a convenience wrapper."""
        ir = _make_bp_first_person_ir()
        text = extract_cpp_constructor(ir)
        assert "ABP_FirstPersonCharacter::ABP_FirstPersonCharacter()" in text
        assert "CreateDefaultSubobject" in text

    def test_sections_from_full_ir(self):
        """build_constructor_sections should categorize all entries correctly."""
        ir = _make_bp_first_person_ir()
        sections = build_constructor_sections(ir)

        assert len(sections["creation"]) == 2
        assert len(sections["attach"]) == 1
        assert len(sections["transform"]) == 1
        assert len(sections["property"]) >= 1
        assert len(sections["load_object"]) == 1


def _make_bp_first_person_ir():
    """Build a mock CppClassIR matching BP_FirstPersonCharacter data."""
    from dataclasses import dataclass

    # Need a minimal mock that looks like CppClassIR
    class MockCppClassIR:
        def __init__(self):
            self.name = "ABP_FirstPersonCharacter"
            self.parent_class = "ACharacter"
            self.properties = []
            self.header_meta = None
            self.methods = []
            self.constructor = {
                "component_creations": [],
                "component_assignments": [],
                "default_values": [],
            }

    ir = MockCppClassIR()

    from uasset_read.models.transforms import VectorValue, RotatorValue

    # Component creations (parent before child in list, but sort should enforce)
    ir.constructor["component_creations"] = [
        CppComponentCreation("FirstPersonMesh", "USkeletalMeshComponent", "FirstPersonMesh"),
        CppComponentCreation("FirstPersonCameraComponent", "UCameraComponent", "FirstPersonCamera"),
    ]

    # Attachments
    ir.constructor["component_assignments"] = [
        CppComponentAssignment("FirstPersonCameraComponent", "FirstPersonMesh", "head"),
    ]

    # Default values (mix of transform, property, load_object)
    ir.constructor["default_values"] = [
        # Transform for camera
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
        # Property: bUsePawnControlRotation
        CppDefaultValue(
            target="FirstPersonCameraComponent->bUsePawnControlRotation",
            value=True,
            cpp_type="bool",
        ),
        # InputAction: JumpAction
        CppDefaultValue(
            target="JumpAction",
            value="/Game/Input/Actions/IA_Jump.IA_Jump",
            cpp_type="UInputAction*",
            needs_load_object=True,
        ),
    ]

    return ir
