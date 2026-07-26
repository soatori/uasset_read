"""C++ constructor text formatter.

Formats IR data from CppClassIR.constructor dictionary into complete C++ constructor text.

Functions:
    build_constructor_sections: Classify constructor IR into 5 code sections
    format_cpp_constructor: Assemble complete constructor text

Security mitigations (threat model):
    T-059-05: Escape quotes and backslashes in string values passed to TEXT()
    T-059-06: Component creation ordered by topological sort (based on attach relationships)
    T-059-07: InputAction asset_path validation for /Game/... pattern
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from uasset_read.cpp_gen.cpp_constructor_ir_builder import (
    CppComponentAssignment,
    CppComponentCreation,
    CppDefaultValue,
)
from uasset_read.cpp_gen.cpp_default_value_formatter import (
    format_cpp_default_value,
    format_cpp_input_action_load,
    format_cpp_transform,
)
from uasset_read.cpp_gen.sanitizer import sanitize_identifier, sanitize_string_literal
from uasset_read.models.transforms import RotatorValue, VectorValue

if TYPE_CHECKING:
    from uasset_read.cpp_gen.formatters.cpp_json_ir import CppClassIR

# ============================================================================
# Constants
# ============================================================================

_SECTION_COMMENTS = {
    "creation": "// Component creation",
    "attach": "// Setup attachments",
    "transform": "// Transform assignments",
    "property": "// Property assignments",
    "load_object": "// InputAction loads",
}

_SECTION_ORDER = ["creation", "attach", "transform", "property", "load_object"]

_INDENT = "    "  # 4-space indent


# ============================================================================
# Topological sort (T-059-06)
# ============================================================================


def _topological_sort_creations(
    creations: List[CppComponentCreation],
    assignments: List[CppComponentAssignment],
) -> List[CppComponentCreation]:
    """Topologically sort component creation order (T-059-06).

    Based on attach relationships: components that are attached to (parent_name) must be created first.

    Args:
        creations: Raw component creation list
        assignments: Attach relationship list

    Returns:
        Topologically sorted component creation list
    """
    if not creations:
        return []

    # Build component name to creation mapping
    name_to_creation = {c.variable_name: c for c in creations}
    all_names = set(name_to_creation.keys())

    # Build dependency graph: child depends on parent (parent must be created first)
    # Note: parent_name in assignments may not be in components (e.g. RootComponent)
    # Only consider components that are in creations
    dependencies: Dict[str, set] = {name: set() for name in all_names}
    for assign in assignments:
        child = assign.child_name
        parent = assign.parent_name
        if child in all_names and parent in all_names:
            dependencies[child].add(parent)

    # Kahn's algorithm
    in_degree = {name: len(deps) for name, deps in dependencies.items()}
    queue = [name for name, deg in in_degree.items() if deg == 0]
    queue.sort()  # Stable sort
    result: List[CppComponentCreation] = []

    while queue:
        node = queue.pop(0)
        result.append(name_to_creation[node])
        for name, deps in dependencies.items():
            if node in deps:
                deps.discard(node)
                in_degree[name] -= 1
                if in_degree[name] == 0:
                    queue.append(name)
                    queue.sort()

    # If there are circular dependencies, append remaining components in original order
    if len(result) < len(creations):
        seen = {c.variable_name for c in result}
        for c in creations:
            if c.variable_name not in seen:
                result.append(c)

    return result


# ============================================================================
# build_constructor_sections
# ============================================================================


def _normalize_transform_keys(transforms: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize transform key names and value types for format_cpp_transform.

    - Renames 'relative_scale3d' → 'relative_scale' (key mismatch fix)
    - Converts dict-based location/rotation to VectorValue/RotatorValue objects
      (build_transform_assignments stores raw dicts, format_cpp_transform expects
      typed value objects).
    """
    result = dict(transforms)
    if "relative_scale3d" in result and "relative_scale" not in result:
        result["relative_scale"] = result.pop("relative_scale3d")

    # Convert dict-based location to VectorValue
    loc = result.get("relative_location")
    if isinstance(loc, dict) and not isinstance(loc, VectorValue):
        result["relative_location"] = VectorValue(
            x=loc.get("X", 0.0),
            y=loc.get("Y", 0.0),
            z=loc.get("Z", 0.0),
        )

    # Convert dict-based rotation to RotatorValue
    rot = result.get("relative_rotation")
    if isinstance(rot, dict) and not isinstance(rot, RotatorValue):
        result["relative_rotation"] = RotatorValue(
            roll=rot.get("Roll", 0.0),
            pitch=rot.get("Pitch", 0.0),
            yaw=rot.get("Yaw", 0.0),
        )

    return result


def build_constructor_sections(ir: "CppClassIR") -> Dict[str, List[str]]:
    """Classify the three lists in the constructor dictionary into annotated code sections.

    Classification logic:
    1. creation: Generate CreateDefaultSubobject calls from component_creations
    2. attach: Generate SetupAttachment calls from component_assignments
    3. transform: Filter default_values for is_method_call=True, method_type="transform"
    4. property: Filter default_values for regular property assignments
    5. load_object: Filter default_values for needs_load_object=True

    Component creation order is topologically sorted (T-059-06).

    Args:
        ir: CppClassIR instance with constructor dictionary populated

    Returns:
        Dictionary containing 5 code sections, each as a list of code line strings
    """
    constructor = ir.constructor
    creations: List[CppComponentCreation] = constructor.get("component_creations", [])
    assignments: List[CppComponentAssignment] = constructor.get("component_assignments", [])
    default_values: List[CppDefaultValue] = constructor.get("default_values", [])

    sections: Dict[str, List[str]] = {
        "creation": [],
        "attach": [],
        "transform": [],
        "property": [],
        "load_object": [],
    }

    # 1. creation section -- topological sort (T-059-06)
    sorted_creations = _topological_sort_creations(creations, assignments)
    for creation in sorted_creations:
        safe_var = sanitize_identifier(creation.variable_name)
        safe_name = sanitize_string_literal(creation.component_name)
        line = (
            f"{safe_var} = "
            f"CreateDefaultSubobject<{creation.cpp_type}>"
            f'(TEXT("{safe_name}"));'
        )
        sections["creation"].append(line)

    # 2. attach section
    for assign in assignments:
        if assign.socket_name:
            safe_socket = sanitize_string_literal(assign.socket_name)
            line = (
                f"{assign.child_name}->SetupAttachment("
                f"{assign.parent_name}, FName(\"{safe_socket}\"));"
            )
        else:
            line = f"{assign.child_name}->SetupAttachment({assign.parent_name});"
        sections["attach"].append(line)

    # 3. transform section -- filter default_values for is_method_call=True, method_type="transform"
    # 4. property section -- filter default_values for regular property assignments
    # 5. load_object section -- filter default_values for needs_load_object=True
    for entry in default_values:
        # T-059-07: InputAction LoadObject
        if entry.needs_load_object:
            try:
                load_line = format_cpp_input_action_load(entry.target, entry.value)
                if load_line:
                    sections["load_object"].append(load_line)
            except ValueError as e:
                # Path validation failed -- log warning and skip
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Skipping LoadObject for '{entry.target}': {e}"
                )
            continue

        # Transform method call
        if entry.is_method_call and entry.method_type == "transform":
            # Normalize scale key for format_cpp_transform compatibility
            normalized_value = _normalize_transform_keys(entry.value)
            transform_lines = format_cpp_transform(normalized_value, entry.target)
            sections["transform"].extend(transform_lines)
            continue

        # Regular property assignment (excluding method calls and LoadObject)
        if not entry.is_method_call and not entry.needs_load_object:
            cpp_value = format_cpp_default_value(entry.value, entry.cpp_type)
            if cpp_value:
                sections["property"].append(f"{entry.target} = {cpp_value};")

    return sections


# ============================================================================
# format_cpp_constructor
# ============================================================================


def format_cpp_constructor(ir: "CppClassIR") -> str:
    """Assemble complete C++ constructor text.

    Output format:
    ```cpp
    ClassName::ClassName()
        : Super::ParentClass()
    {
        // Component creation
        ...

        // Setup attachments
        ...

        // Transform assignments
        ...

        // Property assignments
        ...

        // InputAction loads
        ...
    }
    ```

    - Function signature: ClassName::ClassName()
    - Initializer list: Super::ClassName() (unconditional, D-59-05)
    - Blank line between sections
    - Empty sections are skipped
    - 4-space indent

    Args:
        ir: CppClassIR instance

    Returns:
        Complete C++ constructor text
    """
    sections = build_constructor_sections(ir)

    lines: List[str] = []

    # Function signature
    lines.append(f"{ir.name}::{ir.name}()")

    # Initializer list -- UE5 uses Super() as parent class constructor call
    lines.append("    : Super()")

    # Function body start
    lines.append("{")

    # Output sections in order (skip empty sections)
    first_section = True
    for section_key in _SECTION_ORDER:
        section_lines = sections.get(section_key, [])
        if not section_lines:
            continue

        # Blank line between sections
        if not first_section:
            lines.append("")
        first_section = False

        # Section comment
        lines.append(f"{_INDENT}{_SECTION_COMMENTS[section_key]}")

        # Section code
        for code_line in section_lines:
            # Multi-line statements (e.g. transform multi-line calls) need line-by-line indent
            code_lines = code_line.split("\n")
            for i, cl in enumerate(code_lines):
                if i == 0:
                    lines.append(f"{_INDENT}{cl}")
                else:
                    lines.append(f"{_INDENT}{cl}")

    # Function body end
    lines.append("}")

    return "\n".join(lines)


# ============================================================================
# Export list
# ============================================================================

__all__ = [
    "build_constructor_sections",
    "format_cpp_constructor",
]
