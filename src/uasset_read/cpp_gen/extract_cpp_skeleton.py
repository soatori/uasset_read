from __future__ import annotations

"""
C++ class skeleton extraction module -- extract_cpp_class_skeleton().

Per D-02: Trace inheritance chain along ClassParent.
Per D-03: Use ue_path_to_cpp_type for type mapping.
Per D-04: Use cpf_flags_to_uproperty_marks for UPROPERTY specifiers.
Per D-05: Build complete header_meta.
Extract method declarations from graph nodes to populate methods.
Inject function bodies from decompiled_functions into body_text.

Exports:
    extract_cpp_class_skeleton: PackageIR -> CppClassIR extraction function
"""

import re
import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Tuple

from uasset_read.cpp_gen.formatters import (
    CppClassIR,
    CppProperty,
    CppHeaderMeta,
    CppMethodIR,
    CppCallParameter,
    CppCallStatement,
)
from uasset_read.cpp_gen.cpp_type_mapper import (
    ue_path_to_cpp_type,
    ue_package_path_to_cpp_class,
    infer_class_prefix,
)
from uasset_read.cpp_gen.cpp_uproperty_mapper import (
    cpf_flags_to_uproperty_marks,
)
from uasset_read.cpp_gen.cpp_constructor_ir_builder import (
    build_component_creations,
    build_component_assignments,
    build_default_values,
    build_transform_assignments,
)
from uasset_read.cpp_gen.cpp_constructor_formatter import (
    format_cpp_constructor,
)
from uasset_read.cpp_gen.sanitizer import sanitize_identifier

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, BlueprintIR, VariableIR, DecompiledFunctionIR
    from uasset_read.models.blueprint import BlueprintMetadata, BlueprintVariable
    from uasset_read.models.core import FEdGraphPinType, UEdGraph, UEdGraphPin
    from uasset_read.models.node_types import K2NodeFunctionEntry, K2NodeEvent

logger = logging.getLogger(__name__)

# ============================================================================
# Inheritance chain depth limit (T-056-03)
# ============================================================================

MAX_INHERITANCE_DEPTH = 50  # Prevent infinite loops

# ============================================================================
# Backfill missing methods from decompiled_functions (third path)
# ============================================================================

def _backfill_missing_methods(
    methods: List[CppMethodIR],
    decompiled_functions: List[Any],
) -> None:
    """Backfill CppMethodIR entries missed by extract_cpp_functions from decompiled_functions.

    Reason: extract_cpp_functions only handles K2Node_FunctionEntry and
    K2Node_Event(b_override=True), but some decompiled functions have no corresponding graph nodes
    (e.g. ExecuteUbergraph, UserConstructionScript, InputAction events).
    """
    existing_names = {m.cpp_name for m in methods}
    for decompiled in decompiled_functions:
        func_name = getattr(decompiled, 'function_name', None) or decompiled.name
        sanitized = sanitize_identifier(func_name)
        if sanitized not in existing_names:
            methods.append(CppMethodIR(
                cpp_name=sanitized,
                return_type="void",
                parameters=[],
                ufunction_specifiers=[],
                is_override=False,
                body_text=decompiled.cpp_code or "/* no source available */",
            ))
            existing_names.add(sanitized)

# ============================================================================
# Core extraction functions
# ============================================================================

def extract_cpp_class_skeleton(ir: "PackageIR") -> CppClassIR:
    """Extract C++ class skeleton from PackageIR.

    Per D-02: Trace inheritance chain from BlueprintIR.parent_class.
    Per D-03: Map UE types to C++ type names.
    Per D-04: Convert CPF flags to UPROPERTY specifiers.
    Per D-05: Build header_meta (includes + generated_include).
    Extract method declarations from blueprint function/event IR to populate methods.

    Args:
        ir: PackageIR (from build_package_ir)

    Returns:
        CppClassIR: C++ class skeleton intermediate representation

    Raises:
        ValueError: If ir.blueprint is None
    """
    # Validate input
    if ir.blueprint is None:
        raise ValueError("PackageIR.blueprint is None — cannot extract skeleton")

    blueprint = ir.blueprint

    # 1. Extract class name
    class_name = _extract_class_name(ir)

    # 2. Resolve inheritance chain (Per D-02)
    parent_class = _resolve_parent_class(blueprint, ir.linker)

    # 3. Extract component properties
    properties: List[CppProperty] = []
    component_vars = [v for v in ir.variables if v.kind == "component"]
    properties.extend(_extract_component_properties(component_vars, blueprint.components))

    # 4. Extract variable properties
    user_vars = [v for v in ir.variables if v.kind == "user"]
    properties.extend(_extract_variable_properties(user_vars))

    # 5. Extract input action variables (from IR variables)
    input_vars = [v for v in ir.variables if v.kind == "input_action"]
    if input_vars:
        properties.extend(_extract_input_action_properties_from_ir(input_vars))

    # 6. Extract method declarations (from BlueprintIR functions/events)
    methods: List[CppMethodIR] = []
    methods.extend(_build_methods_from_blueprint_ir(blueprint))

    # 6. Backfill missing methods (third path -- generate CppMethodIR directly from decompiled_functions)
    if ir.decompiled_functions:
        _backfill_missing_methods(methods, ir.decompiled_functions)

    # 6. Inject function bodies (from decompiled_functions)
    if methods and ir.decompiled_functions:
        _inject_function_bodies(methods, ir.decompiled_functions)

    # 6.1 Set class_name (used in .cpp implementation for ClassName::Method prefix)
    for method in methods:
        if not method.class_name:
            method.class_name = class_name

    # 7. Build header_meta (Per D-05)
    header_meta = CppHeaderMeta.build_from_parent(parent_class, class_name)

    # 7. Build CppClassIR
    skeleton = CppClassIR(
        name=class_name,
        parent_class=parent_class,
        header_meta=header_meta,
        properties=properties,
        methods=methods,
        constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [],
        },  # To be populated
    )

    # Populate constructor dictionary
    components = blueprint.components or []
    skeleton.constructor["component_creations"] = build_component_creations(skeleton)
    skeleton.constructor["component_assignments"] = build_component_assignments(components)
    skeleton.constructor["default_values"] = build_default_values(skeleton, ir.variables)

    # Blocker 2 fix: transform data also flows into default_values
    skeleton.constructor["default_values"].extend(build_transform_assignments(skeleton, components))

    # Generate complete constructor text
    skeleton.constructor["constructor_text"] = format_cpp_constructor(skeleton)

    return skeleton

# ============================================================================
# Blueprint metadata filter (P0 improvement)
# ============================================================================

# Blueprint internal metadata properties, should not be output as C++ member variables
BLUEPRINT_METADATA_KEYS = frozenset({
    # Blueprint system properties
    'BlueprintSystemVersion',
    'BlueprintGuid',
    'bLegacyNeedToPurgeSkelRefs',
    'bEnforceConstCorrectness',
    # Construction script
    'SimpleConstructionScript',
    # Graph related
    'UbergraphPages',
    'FunctionGraphs',
    'NewVariables',
    'CategorySorting',
    'LastEditedDocuments',
    'ImplementedInterfaces',
    # Thumbnail and class references
    'ThumbnailInfo',
    'GeneratedClass',
    'PropertyGuids',
    # Ubergraph
    'UbergraphFunction',
    'UbergraphFrame',
})

def _is_blueprint_metadata(prop_name: str) -> bool:
    """Check if property is blueprint internal metadata.

    Args:
        prop_name: Property name

    Returns:
        True if it is blueprint metadata (should be filtered out)
    """
    return prop_name in BLUEPRINT_METADATA_KEYS

# ============================================================================
# Component name cleanup (P1 improvement)
# ============================================================================

# Component name suffix patterns to remove
_COMPONENT_SUFFIX_PATTERNS = [
    (re.compile(r'_GEN_VARIABLE$'), ''),
    (re.compile(r'_\d+__[A-F0-9]+$'), ''),  # _0__CCE3C0B4 etc. hash suffixes
    (re.compile(r'_\d+$'), ''),  # _0 etc. numeric suffixes
]

def _clean_component_name(name: str) -> str:
    """Clean component name, removing UE internal suffixes.

    Examples:
        CameraComponent_0__CCE3C0B4 -> CameraComponent
        FirstPersonMesh_GEN_VARIABLE -> FirstPersonMesh
        Arrow_1 -> Arrow

    Args:
        name: Raw component name

    Returns:
        Cleaned name
    """
    cleaned = name
    for pattern, replacement in _COMPONENT_SUFFIX_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned if cleaned else name

# ============================================================================
# Class name simplification (P0 improvement)
# ============================================================================

def _simplify_class_name(raw_name: str) -> str:
    """Simplify class name, extracting concise name from full package path.

    Examples:
        /Game/FirstPerson/Blueprints/BP_FirstPersonCharacter -> BP_FirstPersonCharacter
        Game_FirstPerson_Blueprints_BP_FirstPersonCharacter -> BP_FirstPersonCharacter

    Args:
        raw_name: Raw name (may contain path)

    Returns:
        Simplified class name
    """
    # Remove path prefix
    if '/' in raw_name:
        raw_name = raw_name.rsplit('/', 1)[-1]

    # Remove dot-separated extension
    if '.' in raw_name:
        raw_name = raw_name.rsplit('.', 1)[0]

    # Replace illegal characters with underscores
    cleaned = re.sub(r'[^A-Za-z0-9_]', '_', raw_name)

    # Ensure it starts with a valid character
    if cleaned and cleaned[0].isdigit():
        cleaned = '_' + cleaned

    return cleaned

# ============================================================================
# Helper functions
# ============================================================================

def _build_param_name_map(method: CppMethodIR) -> Dict[str, str]:
    """Build {original parameter name pattern -> sanitized name} mapping.

    Sanitizer replaces '/' and other illegal characters with '__'. For example:
    - 'Left / Right' -> 'Left__Right'
    - 'Forward / Backward' -> 'Forward__Backward'

    Reverse inference: if sanitized name contains '__', construct the corresponding ' / ' pattern.
    """
    name_map = {}
    for param in method.parameters:
        if '__' in param.name:
            # Reverse infer original name: '__' -> ' / '
            original = param.name.replace('__', ' / ')
            name_map[original] = param.name
    return name_map

def _inject_function_bodies(
    methods: List[CppMethodIR],
    decompiled_functions: List[Any],
) -> None:
    """Inject cpp_code from KismetDecompiledResult into CppMethodIR.body_text.

    Matching logic:
    1. Exact match: function_name == cpp_name
    2. Sanitized match: sanitized function_name == cpp_name
    3. Case-insensitive match

    Symbol mapping replacement is performed before injection to ensure function body
    variable names are consistent with method declarations.

    Args:
        methods: List of CppMethodIR (with method declarations populated)
        decompiled_functions: List of KismetDecompiledResult (containing cpp_code)
    """
    method_index: Dict[str, CppMethodIR] = {m.cpp_name: m for m in methods}

    for decompiled in decompiled_functions:
        func_name = getattr(decompiled, 'function_name', None) or decompiled.name

        # Exact match
        method = method_index.get(func_name)

        # Sanitized match
        if method is None:
            sanitized = sanitize_identifier(func_name)
            method = method_index.get(sanitized)

        # Case-insensitive match
        if method is None:
            for cpp_name, m in method_index.items():
                if func_name.lower() == cpp_name.lower():
                    method = m
                    break

        if method and decompiled.cpp_code:
            body = decompiled.cpp_code
            # Execute symbol mapping replacement: original parameter name -> sanitized name
            for original, sanitized in _build_param_name_map(method).items():
                body = body.replace(original, sanitized)
            method.body_text = body

def _extract_class_name(ir: "PackageIR") -> str:
    """Extract C++ class name.

    Determine C++ prefix based on blueprint name and parent class type:
    - Use infer_class_prefix to derive prefix from parent class name (A/U/F/E/I)
    - If simplified name already has the correct UE prefix, don't add it again
    - Otherwise add the derived prefix

    Args:
        ir: PackageIR

    Returns:
        C++ class name (with prefix)
    """
    # Get name from header.package_name or name_map[0]
    raw_name = ""
    if ir.header and hasattr(ir.header, 'package_name'):
        raw_name = ir.header.package_name
    elif ir.name_map and len(ir.name_map) > 0:
        raw_name = ir.name_map[0]

    if not raw_name:
        logger.warning("Could not determine class name from PackageIR")
        return "UUnknownClass"

    # Simplify class name
    clean_name = _simplify_class_name(raw_name)

    # Derive prefix from parent class (using infer_class_prefix for unified logic)
    parent_class_path = ir.blueprint.parent_class or ""
    parent_cpp = ue_package_path_to_cpp_class(parent_class_path)
    prefix = infer_class_prefix(parent_cpp)

    # If name already has this prefix, don't add it again
    if clean_name.startswith(prefix):
        return clean_name

    return f"{prefix}{clean_name}"

def _resolve_parent_class(
    blueprint: "BlueprintIR",
    linker: Optional[Any]
) -> str:
    """Resolve parent class name.

    Per D-02: Extract from BlueprintIR.parent_class and convert to C++ class name.
    Future support for deep inheritance chain tracing via linker (currently only direct parent).

    Args:
        blueprint: BlueprintIR
        linker: LinkerSummaryIR (optional, for deep tracing)

    Returns:
        C++ parent class name
    """
    parent_path = blueprint.parent_class
    if not parent_path:
        logger.warning("BlueprintIR.parent_class is None — using UObject as default")
        return "UObject"

    return ue_package_path_to_cpp_class(parent_path)

def _extract_component_properties(
    component_vars: List["VariableIR"],
    components: List[Dict]
) -> List[CppProperty]:
    """Extract component properties.

    Filters variables with kind="component" from the VariableIR list,
    and SCS components from the BlueprintIR.components list.

    Args:
        component_vars: List of VariableIR with kind="component"
        components: BlueprintIR.components list

    Returns:
        List of CppProperty (category="component")
    """
    properties: List[CppProperty] = []

    # Extract components from VariableIR
    for var in component_vars:
        prop = _create_component_property(var)
        properties.append(prop)

    # Extract SCS components from BlueprintIR.components (if any)
    for comp in components:
        comp_name = comp.get("name", "")
        comp_class = comp.get("class", "")

        if comp_name and comp_class:
            # P1 improvement: clean component name
            clean_name = _clean_component_name(comp_name)

            # Complete short names to full path (e.g. "ArrowComponent" -> "/Script/Engine.ArrowComponent")
            comp_path = comp_class
            if not comp_path.startswith("/Script/"):
                # Assume Engine type, complete path
                comp_path = f"/Script/Engine.{comp_class}"

            # Build component type (pointer)
            cpp_type = ue_path_to_cpp_type(comp_path)
            if not cpp_type.endswith("*"):
                cpp_type = f"{cpp_type}*"

            # SCS component default specifiers
            marks = ["VisibleAnywhere", "BlueprintReadOnly", "Instanced"]

            prop = CppProperty(
                cpp_type=cpp_type,
                name=clean_name,
                uproperty_marks=marks,
                category="component",
                default_value=None,
            )
            properties.append(prop)

    return properties

def _create_component_property(var: "VariableIR") -> CppProperty:
    """Create component CppProperty from VariableIR.

    P1 improvement: Use _clean_component_name to clean component names.

    Args:
        var: VariableIR (kind="component")

    Returns:
        CppProperty
    """
    # P1 improvement: clean component name
    clean_name = _clean_component_name(var.name)

    # Extract type path from type field
    ue_type = var.type or ""

    # Complete path (if not a full path)
    if ue_type and not ue_type.startswith("/Script/") and not ue_type.startswith("/"):
        ue_type = f"/Script/Engine.{ue_type}"

    # Convert to C++ type (components are pointers)
    cpp_type = ue_path_to_cpp_type(ue_type)
    if not cpp_type.endswith("*"):
        cpp_type = f"{cpp_type}*"

    # Get UPROPERTY specifiers (component mode)
    marks = cpf_flags_to_uproperty_marks(var.property_flags, is_component=True)

    return CppProperty(
        cpp_type=cpp_type,
        name=clean_name,
        uproperty_marks=marks,
        category="component",
        default_value=None,  # Components have no default value
        cpp_comment=f"UE type: {ue_type}",
    )

def _extract_variable_properties(user_vars: List["VariableIR"]) -> List[CppProperty]:
    """Extract variable properties.

    Filters variables with kind="user" from the VariableIR list.
    P0 improvement: Filter blueprint internal metadata properties.

    Args:
        user_vars: List of VariableIR with kind="user"

    Returns:
        List of CppProperty (category="variable")
    """
    properties: List[CppProperty] = []

    for var in user_vars:
        # P0 improvement: filter blueprint metadata
        if _is_blueprint_metadata(var.name):
            continue
        prop = _create_variable_property(var)
        properties.append(prop)

    return properties

def _extract_input_action_properties(graphs: List["UEdGraph"]) -> List[CppProperty]:
    """Extract input action variables from graph nodes.

    P2 improvement: Extract input action references from K2Node_EnhancedInputAction nodes,
    generating UInputAction* member variables.

    Args:
        graphs: List of graphs

    Returns:
        List of CppProperty (category="input")
    """
    properties: List[CppProperty] = []
    seen_actions: set = set()

    for graph in graphs:
        for node in graph.nodes:
            if node.class_name != "K2Node_EnhancedInputAction":
                continue

            nd = node.node_data
            if not isinstance(nd, dict):
                continue

            # Get input action reference
            action_path = nd.get("input_action_path", "")
            action_short_name = nd.get("input_action_short_name", "")

            if not action_path or action_path == "None":
                continue

            # Deduplicate (same input action may be referenced by multiple nodes)
            if action_path in seen_actions:
                continue
            seen_actions.add(action_path)

            # Generate variable name (use short name)
            var_name = action_short_name if action_short_name else action_path

            # Build property
            prop = CppProperty(
                cpp_type="UInputAction*",
                name=var_name,
                uproperty_marks=["EditAnywhere"],
                category="input",
                default_value=None,
                cpp_comment=f"Input Action: {action_path}",
            )
            properties.append(prop)

    return properties

def _create_variable_property(var: "VariableIR") -> CppProperty:
    """Create variable CppProperty from VariableIR.

    Args:
        var: VariableIR (kind="user")

    Returns:
        CppProperty
    """
    # Get UE type path from type field
    ue_type = var.type or ""

    # Convert to C++ type
    cpp_type = ue_path_to_cpp_type(ue_type)

    # Get UPROPERTY specifiers (variable mode)
    marks = cpf_flags_to_uproperty_marks(var.property_flags, is_component=False)

    return CppProperty(
        cpp_type=cpp_type,
        name=sanitize_identifier(var.name),
        uproperty_marks=marks,
        category="variable",
        default_value=var.default_value,
        cpp_comment=f"UE type: {ue_type}",
    )

def _extract_input_action_properties_from_ir(
    input_vars: List["VariableIR"],
) -> List[CppProperty]:
    """Extract input action properties from VariableIR list.

    Generates UInputAction* member variables from kind="input_action" VariableIR.

    Args:
        input_vars: List of VariableIR with kind="input_action"

    Returns:
        List of CppProperty (category="input")
    """
    properties: List[CppProperty] = []

    for var in input_vars:
        action_path = var.type or ""
        var_name = var.name

        prop = CppProperty(
            cpp_type="UInputAction*",
            name=var_name,
            uproperty_marks=["EditAnywhere"],
            category="input",
            default_value=None,
            cpp_comment=f"Input Action: {action_path}",
        )
        properties.append(prop)

    return properties

def _build_methods_from_blueprint_ir(blueprint: "BlueprintIR") -> List[CppMethodIR]:
    """Build CppMethodIR list from BlueprintIR functions and events.

    Args:
        blueprint: BlueprintIR

    Returns:
        List of CppMethodIR
    """
    methods: List[CppMethodIR] = []

    # Build methods from functions
    for func in blueprint.functions:
        parameters = [
            CppCallParameter(
                name=sanitize_identifier(p.get("name", "")),
                cpp_type=ue_path_to_cpp_type(p.get("type", "")),
                direction="input" if p.get("is_input", True) else "output",
            )
            for p in func.parameters
        ]

        # Infer UFUNCTION specifiers
        specifiers: List[str] = []
        if func.is_pure:
            specifiers.append("BlueprintPure")
        elif func.is_blueprint_callable:
            specifiers.append("BlueprintCallable")

        # Determine access modifier
        access_modifier = "public"
        if func.access_specifier:
            access_modifier = func.access_specifier.lower()

        methods.append(CppMethodIR(
            cpp_name=sanitize_identifier(func.name),
            return_type=func.return_type or "void",
            parameters=parameters,
            ufunction_specifiers=specifiers,
            is_override=False,
            is_const=func.is_const,
            is_static=func.is_static,
            is_pure=func.is_pure,
            access_modifier=access_modifier,
            source_node_type="BlueprintFunctionIR",
        ))

    # Build methods from events
    for event in blueprint.events:
        parameters = [
            CppCallParameter(
                name=sanitize_identifier(p.get("name", "")),
                cpp_type=ue_path_to_cpp_type(p.get("type", "")),
                direction="input" if p.get("is_input", True) else "output",
            )
            for p in event.parameters
        ]

        methods.append(CppMethodIR(
            cpp_name=sanitize_identifier(event.name),
            return_type="void",
            parameters=parameters,
            ufunction_specifiers=[],
            is_override=event.is_override,
            source_node_type="BlueprintEventIR",
        ))

    return methods

def _build_ue_type_from_pin_type(pin_type: "FEdGraphPinType") -> str:
    """Build UE type path from FEdGraphPinType."""
    category = pin_type.pin_category
    subcategory = pin_type.pin_subcategory or ""

    # Property types -> map to corresponding UE basic types
    _PROP_TYPE_MAP = {
        "IntProperty": "int32", "FloatProperty": "float", "DoubleProperty": "double",
        "BoolProperty": "bool",
        "StrProperty": "FString", "NameProperty": "FName", "TextProperty": "FText",
    }
    if category in _PROP_TYPE_MAP:
        return _PROP_TYPE_MAP[category]
    if category in ("ObjectProperty", "SoftObjectProperty"):
        cpp_type = subcategory or "UObject"
        return cpp_type if cpp_type.endswith("*") else f"{cpp_type}*"
    if category in ("ArrayProperty", "SetProperty", "MapProperty"):
        return subcategory or "FString"

    # Basic types returned directly
    _BASIC_TYPES = frozenset({"float", "double", "bool", "int", "int32", "int64",
                               "byte", "string", "name", "text"})
    if category in _BASIC_TYPES:
        return category

    # object types
    if category == "object":
        if subcategory:
            return subcategory if subcategory.startswith("/Script/") else f"/Script/Engine.{subcategory}"
        return "UObject"

    # struct types
    if category in ("struct", "StructProperty"):
        if subcategory:
            return subcategory if subcategory.startswith("/Script/") else f"/Script/CoreUObject.{subcategory}"
        return "FStruct"

    return category

# ============================================================================
# Function signature mapping
# ============================================================================

# --- Helper functions (Plan 02) ---

def _extract_cpp_type_from_pin(pin: "UEdGraphPin") -> Optional[str]:
    """Convert a single pin to a C++ type string.

    Returns None to indicate it should be skipped (exec/delegate pins).
    """
    if pin.pin_type is None:
        return None
    pt = pin.pin_type
    if pt.pin_category in ("exec", "delegate"):
        return None

    # Get base type
    if pt.pin_category in ("object", "struct"):
        # Try to resolve pin_subcategory_object
        if pt.pin_subcategory_object and isinstance(pt.pin_subcategory_object, int):
            # Can be resolved with linker, use pin_subcategory as fallback here
            raw_path = pt.pin_subcategory
        else:
            raw_path = pt.pin_subcategory
        if not raw_path:
            raw_path = pt.pin_category
    else:
        raw_path = pt.pin_subcategory or pt.pin_category

    cpp_type = ue_path_to_cpp_type(raw_path)

    # Add pointer for object types
    if pt.pin_category == "object" and not cpp_type.endswith("*"):
        cpp_type = f"{cpp_type}*"

    # Direction modifier
    if pt.is_reference and pt.is_const:
        cpp_type = f"const {cpp_type}&"
    elif pt.is_reference:
        cpp_type = f"{cpp_type}&"

    return cpp_type

def _extract_parameters_from_pins(
    pins: List["UEdGraphPin"],
    is_event: bool = False
) -> List[CppCallParameter]:
    """Extract function parameters from pin list."""
    params: List[CppCallParameter] = []
    for pin in pins:
        if pin.pin_type is None:
            continue
        pt = pin.pin_type
        # Skip exec / delegate
        if pt.pin_category in ("exec", "delegate"):
            continue
        # Skip hidden pins
        if pin.hidden:
            continue
        # Event nodes skip OutputDelegate and then
        if is_event and pin.pin_name in ("OutputDelegate", "then"):
            continue

        cpp_type = _extract_cpp_type_from_pin(pin)
        if cpp_type is None:
            continue

        params.append(CppCallParameter(
            name=sanitize_identifier(pin.pin_name),
            cpp_type=cpp_type,
            direction="input" if pin.direction == 0 else "output",
        ))
    return params

# ============================================================================
# Function flag constants (UE5 UFunctionFlags) - reference EFunctionFlags.cs
# ============================================================================

# Access modifiers (these flags are not in extra_flags, need to be inferred from other sources)
FUNC_PUBLIC = 0x00000001  # Placeholder, actual access modifier needs inference from other information
FUNC_PROTECTED = 0x00000002  # Placeholder
FUNC_PRIVATE = 0x00000004  # Placeholder

# Function types (reference EFunctionFlags.cs)
FUNC_Final = 0x00000001
FUNC_RequiredAPI = 0x00000002
FUNC_BlueprintAuthorityOnly = 0x00000004
FUNC_BlueprintCosmetic = 0x00000008
FUNC_Net = 0x00000010
FUNC_NetReliable = 0x00000020
FUNC_Simulated = 0x00000040
FUNC_Exec = 0x00000100
FUNC_Native = 0x00000200
FUNC_Event = 0x00000400
FUNC_NetMulticast = 0x00000800
FUNC_UbergraphFunction = 0x00001000
FUNC_Static = 0x00002000
FUNC_MulticastDelegate = 0x00004000
FUNC_Delegate = 0x00008000
FUNC_HasDefaults = 0x00010000
FUNC_HasOutParms = 0x00020000
FUNC_BlueprintCallable = 0x00040000
FUNC_BlueprintPure = 0x00080000
FUNC_EditorOnly = 0x00100000
FUNC_Const = 0x00200000
FUNC_NetValidate = 0x00400000
FUNC_BlueprintEvent = 0x08000000

def _extractFunctionFlags(flags: int) -> Dict[str, bool]:
    """Extract function flags from extra_flags.

    Reference EFunctionFlags.cs definition.

    Args:
        flags: extra_flags value

    Returns:
        Function flags dictionary
    """
    return {
        # Access modifiers (C++ default public)
        "is_public": True,  # Default
        "is_protected": False,  # Default
        "is_private": False,
        # Function types
        "is_blueprint_pure": bool(flags & FUNC_BlueprintPure),
        "is_blueprint_callable": bool(flags & FUNC_BlueprintCallable),
        "is_const": bool(flags & FUNC_Const),
        "is_static": bool(flags & FUNC_Static),
        "is_event": bool(flags & FUNC_Event),
        "is_blueprint_event": bool(flags & FUNC_BlueprintEvent),
        "is_final": bool(flags & FUNC_Final),
        "is_native": bool(flags & FUNC_Native),
    }

def _infer_ufunction_specifiers(
    pins: List["UEdGraphPin"],
    is_override: bool,
    extra_flags: int = 0
) -> List[str]:
    """Infer UFUNCTION specifiers (D-57-03).

    Improvement: Extract flags from extra_flags.
    """
    if is_override:
        return []

    # Extract flags from extra_flags
    flags = _extractFunctionFlags(extra_flags)

    # If extra_flags already has BlueprintPure/BlueprintCallable set, use directly
    if flags["is_blueprint_pure"]:
        return ["BlueprintPure"]
    if flags["is_blueprint_callable"]:
        return ["BlueprintCallable"]

    # Fallback to pin-based inference
    has_exec_input = any(
        p for p in pins
        if p.pin_type and p.pin_type.pin_category == "exec" and p.direction == 0
    )
    has_exec_output = any(
        p for p in pins
        if p.pin_type and p.pin_type.pin_category == "exec" and p.direction == 1
    )
    if has_exec_input or has_exec_output:
        return ["BlueprintCallable"]
    return ["BlueprintPure"]

def _build_cpp_method_from_entry(
    fe_node: "K2NodeFunctionEntry",
    blueprint_functions: Dict
) -> CppMethodIR:
    """Build CppMethodIR from K2Node_FunctionEntry.

    Improvement: Extract function flags from extra_flags.
    """
    # Get function_reference from node_data (may be in node_data dictionary)
    func_ref = getattr(fe_node, 'function_reference', None)
    extra_flags = 0
    if fe_node.node_data:
        if isinstance(fe_node.node_data, dict):
            func_ref = fe_node.node_data.get('function_reference', func_ref)
            extra_flags = fe_node.node_data.get('extra_flags', 0)
        else:
            func_ref = getattr(fe_node.node_data, 'function_reference', func_ref)
            extra_flags = getattr(fe_node.node_data, 'extra_flags', 0)

    if func_ref is None:
        return None

    func_name = func_ref.member_name
    if not func_name or func_name == "None":
        return None

    # Extract function flags
    flags = _extractFunctionFlags(extra_flags)

    # Dual-source cross-validation (D-57-01)
    bp_func = blueprint_functions.get(func_name)
    if bp_func:
        return_type = bp_func.return_type or "void"
        parameters = [
            CppCallParameter(
                name=sanitize_identifier(p.name),
                cpp_type=ue_path_to_cpp_type(p.param_type),
                direction="input" if p.is_input else "output",
            )
            for p in bp_func.parameters
        ]
    else:
        # Fallback from pins
        parameters = _extract_parameters_from_pins(fe_node.pins)
        return_type = "void"

    specifiers = _infer_ufunction_specifiers(
        fe_node.pins,
        is_override=False,
        extra_flags=extra_flags
    )

    # Determine access modifier
    access_modifier = "protected"  # Default
    if flags["is_public"]:
        access_modifier = "public"
    elif flags["is_private"]:
        access_modifier = "private"

    return CppMethodIR(
        cpp_name=sanitize_identifier(func_name),
        return_type=return_type,
        parameters=parameters,
        ufunction_specifiers=specifiers,
        is_override=False,
        is_const=flags["is_const"],
        is_static=flags["is_static"],
        is_pure=flags["is_blueprint_pure"],
        is_event=flags["is_event"],
        is_native=flags["is_native"],
        access_modifier=access_modifier,
        source_node_type="K2Node_FunctionEntry",
    )

def _build_cpp_method_from_event(event_node: "K2NodeEvent") -> CppMethodIR:
    """Build CppMethodIR from K2Node_Event (is_override=True)."""
    # Get event_reference from node_data
    event_ref = None
    nd = event_node.node_data

    if nd is not None:
        if isinstance(nd, dict):
            # Dictionary format: get directly from dictionary
            event_ref = nd.get('event_reference')
        else:
            # Object format: use getattr
            event_ref = getattr(nd, 'event_reference', None)

    # Try to get from node attribute
    if event_ref is None:
        event_ref = getattr(event_node, 'event_reference', None)

    if event_ref is None:
        return None

    event_name = event_ref.member_name if hasattr(event_ref, 'member_name') else None
    if not event_name or event_name == "None":
        return None

    parameters = _extract_parameters_from_pins(event_node.pins, is_event=True)

    return CppMethodIR(
        cpp_name=sanitize_identifier(event_name),
        return_type="void",
        parameters=parameters,
        ufunction_specifiers=[],
        is_override=True,
        source_node_type="K2Node_Event",
    )

# --- Main entry (Plan 02) ---

def extract_cpp_functions(
    graphs: List["UEdGraph"],
    blueprint_functions: Optional[List] = None,
    linker: Optional[Any] = None,
) -> List[CppMethodIR]:
    """Extract C++ method declarations from function graph nodes.

    Iterates all graphs, extracting K2Node_FunctionEntry and K2Node_Event(b_override_function=True).
    """
    bp_lookup: Dict = {}
    if blueprint_functions:
        for func in blueprint_functions:
            bp_lookup[func.name] = func

    methods: List[CppMethodIR] = []
    for graph in graphs:
        for node in graph.nodes:
            if node.class_name == "K2Node_FunctionEntry":
                method = _build_cpp_method_from_entry(node, bp_lookup)
                if method:
                    methods.append(method)
            elif node.class_name == "K2Node_Event":
                # Check b_override_function (may be in node_data)
                b_override = False
                nd = node.node_data
                if isinstance(nd, dict):
                    b_override = nd.get('b_override_function', False)
                else:
                    b_override = getattr(node, 'b_override_function', False)

                if b_override:
                    method = _build_cpp_method_from_event(node)
                    if method:
                        methods.append(method)
    return methods

# --- Call statement extraction (Plan 03) ---

def _derive_call_target(
    pins: List["UEdGraphPin"],
    b_self_context: bool
) -> Tuple[str, str]:
    """Derive call target.

    b_self_context=True -> ("this", "this")
    b_self_context=False -> derive type from self pin
    """
    if b_self_context:
        return ("this", "this")

    # Find self pin
    for pin in pins:
        if pin.pin_name == "self" and pin.pin_type:
            pt = pin.pin_type
            if pt.pin_category == "object":
                raw_path = pt.pin_subcategory
                if raw_path:
                    cpp_type = ue_path_to_cpp_type(raw_path)
                    return (cpp_type, "pointer")
    return ("Unknown", "pointer")

def extract_cpp_call_statements(
    graphs: List["UEdGraph"],
    linker: Optional[Any] = None,
) -> List[CppCallStatement]:
    """Extract C++ call statement references from K2Node_CallFunction nodes."""
    statements: List[CppCallStatement] = []
    for graph in graphs:
        for node in graph.nodes:
            if node.class_name != "K2Node_CallFunction":
                continue

            # Get function_reference
            func_ref = getattr(node, 'function_reference', None)
            if func_ref is None:
                continue
            member_name = getattr(func_ref, 'member_name', None)
            if not member_name or member_name == "None":
                continue

            b_self_context = getattr(func_ref, 'b_self_context', True)
            target, target_type = _derive_call_target(node.pins, b_self_context)

            # Extract arguments (skip exec/then/self)
            args = []
            for pin in node.pins:
                if pin.pin_type and pin.pin_type.pin_category == "exec":
                    continue
                if pin.pin_name in ("self", "then"):
                    continue
                args.append(sanitize_identifier(pin.pin_name))

            statements.append(CppCallStatement(
                method_name=member_name,
                target=target,
                target_type=target_type,
                args=args,
                is_self_context=b_self_context,
            ))
    return statements

# ============================================================================
# Constructor extraction
# ============================================================================

def extract_cpp_constructor(ir: "CppClassIR") -> str:
    """Generate complete C++ constructor text from CppClassIR.

    Convenience function that calls format_cpp_constructor to generate constructor code.

    Args:
        ir: CppClassIR instance (constructor dictionary populated)

    Returns:
        Complete C++ constructor text
    """
    return format_cpp_constructor(ir)

# ============================================================================
# Export list
# ============================================================================

__all__ = [
    "extract_cpp_class_skeleton",
    "extract_cpp_functions",
    "extract_cpp_call_statements",
    "extract_cpp_constructor",
    "_sanitize_identifier",
    "_derive_call_target",
]
