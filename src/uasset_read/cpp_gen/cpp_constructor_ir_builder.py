"""
Constructor IR builder module.

Extracts data from CppClassIR.properties, component data, and blueprint.variables
to populate the component_creations, component_assignments, and default_values
lists in CppClassIR.constructor dictionary.

Data models:
    CppComponentCreation: CreateDefaultSubobject call
    CppComponentAssignment: SetupAttachment call
    CppDefaultValue: Property assignment (including transform method calls)

Builder functions:
    build_component_creations: Extract component creation from ir.properties
    build_component_assignments: Extract attach relationships from components data
    build_default_values: Extract default values from ir.properties and blueprint_vars
    build_transform_assignments: Extract transform data from component transforms
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from uasset_read.cpp_gen.formatters.cpp_json_ir import CppClassIR
    from uasset_read.models.blueprint import BlueprintVariable
    from uasset_read.models.ir import VariableIR


from uasset_read.constants import BLUEPRINT_METADATA_KEYS as _BLUEPRINT_METADATA_KEYS


def _is_blueprint_metadata(var_name: str) -> bool:
    """Check if variable name is a blueprint metadata key."""
    return var_name in _BLUEPRINT_METADATA_KEYS


# ============================================================================
# Data models
# ============================================================================


@dataclass
class CppComponentCreation:
    """CreateDefaultSubobject call.

    Represents creating a component instance in a C++ constructor:
    ```cpp
    FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FirstPersonMesh"));
    ```

    Attributes:
        variable_name: C++ variable name (e.g. "FirstPersonMesh")
        cpp_type: Dereferenced C++ type (e.g. "USkeletalMeshComponent")
        component_name: TEXT() parameter (e.g. "FirstPersonMesh")
    """
    variable_name: str
    cpp_type: str
    component_name: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return {
            "variable_name": self.variable_name,
            "cpp_type": self.cpp_type,
            "component_name": self.component_name,
        }


@dataclass
class CppComponentAssignment:
    """SetupAttachment call.

    Represents attaching a child component to a parent component in a C++ constructor:
    ```cpp
    FirstPersonCameraComponent->SetupAttachment(FirstPersonMesh, TEXT("head"));
    ```

    Attributes:
        child_name: Child component variable name
        parent_name: Parent component variable name
        socket_name: Socket name (can be empty string)
    """
    child_name: str
    parent_name: str
    socket_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return {
            "child_name": self.child_name,
            "parent_name": self.parent_name,
            "socket_name": self.socket_name,
        }


@dataclass
class CppDefaultValue:
    """Property assignment or method call assignment.

    Represents setting a property value or calling a method in a C++ constructor:
    - Regular assignment: `TargetArmLength = 400.0f;`
    - Method call: `GetCapsuleComponent()->InitCapsuleSize(55.f, 96.0f);`
    - Transform: `FirstPersonCameraComponent->SetRelativeLocationAndRotation(...);`
    - LoadObject: `IA_JumpAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/..."));`

    Attributes:
        target: Assignment target (e.g. "FirstPersonCameraComponent->bUsePawnControlRotation")
        value: Formatted value string
        cpp_type: C++ type (e.g. "float", "bool", "transform")
        is_method_call: Whether this is a method call assignment
        method_type: Method call type classification ("transform" for transform assignments, empty string for regular assignments)
        needs_load_object: Whether LoadObject loading is needed (UInputAction* and similar data assets marked True)
    """
    target: str
    value: str
    cpp_type: str
    is_method_call: bool = False
    method_type: str = ""
    needs_load_object: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        result: Dict[str, Any] = {
            "target": self.target,
            "value": self.value,
            "cpp_type": self.cpp_type,
        }
        if self.is_method_call:
            result["is_method_call"] = True
        if self.method_type:
            result["method_type"] = self.method_type
        if self.needs_load_object:
            result["needs_load_object"] = True
        return result


# ============================================================================
# Builder functions
# ============================================================================


def build_component_creations(ir: "CppClassIR") -> List[CppComponentCreation]:
    """Extract component creation information from CppClassIR.properties.

    Iterates ir.properties, filters entries where category == "component",
    and generates CppComponentCreation for each component.

    Special handling:
    - UInputAction* types are skipped (they exist as data assets, not using CreateDefaultSubobject)

    Args:
        ir: CppClassIR instance

    Returns:
        List of CppComponentCreation
    """
    creations: List[CppComponentCreation] = []

    for prop in ir.properties:
        if prop.category != "component":
            continue

        # D-59-06: InputAction special handling -- skip CreateDefaultSubobject
        if prop.cpp_type == "UInputAction*":
            logger.debug(
                f"Skipping CreateDefaultSubobject for InputAction component: {prop.name}"
            )
            continue

        cpp_type = prop.cpp_type.rstrip("*").strip()
        creations.append(CppComponentCreation(
            variable_name=prop.name,
            cpp_type=cpp_type,
            component_name=prop.name,
        ))

    logger.info(
        f"Built {len(creations)} component creations for class '{ir.name}'"
    )
    return creations


def build_component_assignments(
    components: List[Dict[str, Any]]
) -> List[CppComponentAssignment]:
    """Extract attach relationships from component data.

    Iterates the components list (from extract_components output),
    checking each component for the attach_parent field.

    Args:
        components: List of component dictionaries, each containing name/class/properties/transforms keys,
                    may contain attach_parent/attach_socket_name fields

    Returns:
        List of CppComponentAssignment
    """
    assignments: List[CppComponentAssignment] = []

    for comp in components:
        # Support multiple field naming conventions
        attach_parent = (
            comp.get("attach_parent")
            or comp.get("AttachParent")
            or comp.get("properties", {}).get("AttachParent")
        )

        if not attach_parent:
            continue

        child_name = comp.get("name", "")
        if not child_name:
            continue

        # Map Root/RootComponent -> RootComponent
        parent_name = attach_parent
        if parent_name in ("Root", "RootComponent", "root"):
            parent_name = "RootComponent"

        # Extract socket name
        socket_name = (
            comp.get("attach_socket_name")
            or comp.get("AttachSocketName")
            or comp.get("properties", {}).get("AttachSocketName", "")
        )

        assignments.append(CppComponentAssignment(
            child_name=child_name,
            parent_name=parent_name,
            socket_name=socket_name or "",
        ))

    logger.info(f"Built {len(assignments)} component assignments")
    return assignments


def build_default_values(
    ir: "CppClassIR",
    blueprint_vars: Optional[List["VariableIR"]] = None,
) -> List[CppDefaultValue]:
    """Extract default values from CppClassIR.properties and VariableIR list.

    Iterates entries in ir.properties where category == "variable", and optionally
    the VariableIR list, generating CppDefaultValue entries.

    Special handling:
    - UInputAction* types: Mark needs_load_object=True (requires LoadObject loading)
    - Non-InputAction variables with default_value None: Skip
    - T-059-02: Filter potential injection characters in value (;, {}, //)

    Args:
        ir: CppClassIR instance
        blueprint_vars: Optional VariableIR list

    Returns:
        List of CppDefaultValue
    """
    defaults: List[CppDefaultValue] = []

    # Extract variable default values from ir.properties
    for prop in ir.properties:
        if prop.category != "variable":
            continue

        # InputAction special handling
        if prop.cpp_type == "UInputAction*":
            if prop.default_value and str(prop.default_value).strip():
                defaults.append(CppDefaultValue(
                    target=prop.name,
                    value=str(prop.default_value),
                    cpp_type=prop.cpp_type,
                    needs_load_object=True,
                ))
                logger.debug(
                    f"InputAction variable '{prop.name}' marked with needs_load_object=True"
                )
            continue

        # Regular variables -- skip those without default values
        if prop.default_value is None:
            continue

        value_str = _sanitize_value(str(prop.default_value), prop.cpp_type)
        defaults.append(CppDefaultValue(
            target=prop.name,
            value=value_str,
            cpp_type=prop.cpp_type,
        ))

    # Supplement extraction from VariableIR list
    if blueprint_vars:
        for var in blueprint_vars:
            # Compatible with both VariableIR (kind) and BlueprintVariable (is_component)
            is_comp = getattr(var, 'kind', None) == "component" or getattr(var, 'is_component', False)
            if is_comp:
                continue
            if var.default_value is None:
                continue
            var_name = getattr(var, 'name', None) or getattr(var, 'var_name', '')
            if _is_blueprint_metadata(var_name):
                continue

            # Skip variables already processed in ir.properties
            already_processed = any(
                d.target == var_name for d in defaults
            )
            if already_processed:
                continue

            cpp_type = _variable_type_to_cpp(var)
            value_str = _sanitize_value(str(var.default_value), cpp_type)
            defaults.append(CppDefaultValue(
                target=var_name,
                value=value_str,
                cpp_type=cpp_type,
            ))

    logger.info(f"Built {len(defaults)} default values")
    return defaults


def build_transform_assignments(
    ir: "CppClassIR",
    components: List[Dict[str, Any]],
) -> List[CppDefaultValue]:
    """Extract transform assignments from component transforms data into IR.

    Iterates the components list, checking each component's transforms dictionary
    for keys like relative_location or relative_rotation. If present,
    creates CppDefaultValue entries with is_method_call=True, method_type="transform".

    Blocker 2 fix: transform data flows into IR default_values.

    Args:
        ir: CppClassIR instance
        components: List of component dictionaries

    Returns:
        List of CppDefaultValue (is_method_call=True, method_type="transform")
    """
    entries: List[CppDefaultValue] = []

    for comp in components:
        transforms = comp.get("transforms", {})
        if not transforms:
            continue

        has_loc = "relative_location" in transforms
        has_rot = "relative_rotation" in transforms
        has_scale = "relative_scale3d" in transforms

        if not has_loc and not has_rot and not has_scale:
            continue

        comp_name = comp.get("name", "")
        if not comp_name:
            continue

        entries.append(CppDefaultValue(
            target=comp_name,
            value=transforms,
            cpp_type="transform",
            is_method_call=True,
            method_type="transform",
        ))

    logger.info(f"Built {len(entries)} transform assignments")
    return entries


# ============================================================================
# Helper functions
# ============================================================================


def _sanitize_value(value: str, cpp_type: str) -> str:
    """T-059-02: Sanitize value string to prevent code injection.

    Rejects values containing ;, {, }, // (which could be used to inject C++ code).
    For detected dangerous values, returns a sanitized version (dangerous characters removed) and logs a warning.

    Args:
        value: Raw value string
        cpp_type: C++ type (for context)

    Returns:
        Sanitized value string
    """
    dangerous_chars = [";", "{", "}"]
    dangerous_patterns = ["//"]

    has_danger = False
    for ch in dangerous_chars:
        if ch in value:
            has_danger = True
            break
    for pat in dangerous_patterns:
        if pat in value:
            has_danger = True
            break

    if has_danger:
        logger.warning(
            f"Potentially dangerous value for type {cpp_type}: "
            f"{value!r} — sanitizing"
        )
        # Remove dangerous characters
        cleaned = value
        for ch in dangerous_chars:
            cleaned = cleaned.replace(ch, "")
        for pat in dangerous_patterns:
            cleaned = cleaned.replace(pat, "")
        return cleaned.strip()

    return value


def _variable_type_to_cpp(var: Any) -> str:
    """Derive C++ type from VariableIR or BlueprintVariable.

    Supports VariableIR (type field is str) and BlueprintVariable (var_type is FEdGraphPinType).

    Args:
        var: VariableIR or BlueprintVariable instance

    Returns:
        C++ type string
    """
    from uasset_read.cpp_gen.cpp_type_mapper import ue_path_to_cpp_type

    # VariableIR: type field is str
    if hasattr(var, 'type') and isinstance(var.type, str):
        ue_type = var.type
        if not ue_type:
            return "FString"
        cpp_type = ue_path_to_cpp_type(ue_type)
        return cpp_type

    # BlueprintVariable: var_type is FEdGraphPinType
    var_type = getattr(var, 'var_type', None)
    category = var_type.pin_category if var_type else ""
    subcategory = var_type.pin_subcategory if var_type else ""

    # Basic type mapping
    type_map = {
        "FloatProperty": "float",
        "DoubleProperty": "double",
        "IntProperty": "int32",
        "Int64Property": "int64",
        "BoolProperty": "bool",
        "StrProperty": "FString",
        "NameProperty": "FName",
        "TextProperty": "FText",
        "ByteProperty": "uint8",
    }

    if category in type_map:
        return type_map[category]

    # object types
    if category in ("object", "ObjectProperty", "SoftObjectProperty"):
        if subcategory:
            cpp_type = ue_path_to_cpp_type(subcategory)
            if not cpp_type.endswith("*"):
                cpp_type = f"{cpp_type}*"
            return cpp_type
        return "UObject*"

    # struct types
    if category in ("struct", "StructProperty"):
        if subcategory:
            cpp_type = ue_path_to_cpp_type(subcategory)
            return cpp_type
        return "FName"

    # Fallback
    if category:
        return ue_path_to_cpp_type(category)
    return "FString"


# ============================================================================
# Export list
# ============================================================================

__all__ = [
    "CppComponentCreation",
    "CppComponentAssignment",
    "CppDefaultValue",
    "build_component_creations",
    "build_component_assignments",
    "build_default_values",
    "build_transform_assignments",
]
