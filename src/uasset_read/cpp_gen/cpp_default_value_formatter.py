"""C++ default value formatter -- converts Python values to type-correct C++ literals.

Provides type-safe value formatting tools for the constructor generator.

Security mitigations (threat model T-059-03, T-059-04):
- Quote escaping in string values
- Reject values containing C++ syntax tokens (;, {, }, //)
- InputAction asset_path validation for /Game/... pattern
"""

import re
from typing import Any, Dict, List, Optional


# ============================================================================
# Security constants (T-059-03)
# ============================================================================

# Reject values containing these C++ syntax tokens
CPP_SYNTAX_TOKENS = [';', '{', '}', '//']

# UE asset path pattern (T-059-04)
UE_ASSET_PATH_PATTERN = re.compile(r'^/Game/')


def _escape_cpp_string(value: str) -> str:
    """Escape string values to prevent C++ injection (T-059-03).

    Args:
        value: Raw string value

    Returns:
        Escaped string value
    """
    # Escape backslashes (must be done first)
    value = value.replace('\\', '\\\\')
    # Escape double quotes
    value = value.replace('"', '\\"')
    # Escape control characters
    value = value.replace('\n', '\\n')
    value = value.replace('\r', '\\r')
    value = value.replace('\t', '\\t')
    return value


def _validate_no_cpp_syntax(value: str) -> str:
    """Validate that string value does not contain C++ syntax tokens (T-059-03).

    Args:
        value: String value to validate

    Returns:
        Original value (if safe)

    Raises:
        ValueError: If value contains C++ syntax tokens
    """
    for token in CPP_SYNTAX_TOKENS:
        if token in value:
            raise ValueError(
                f"Value contains C++ syntax token '{token}': {value!r}"
            )
    return value


def _format_float_value(value: float) -> str:
    """Format float value as C++ literal (55.f format).

    - Integer values: `55.f`
    - With decimal part: `400.12f`

    Args:
        value: Floating point value

    Returns:
        C++ float literal string
    """
    fval = float(value)
    if fval == int(fval):
        return f"{int(fval)}.f"
    return f"{fval}f"


def format_cpp_default_value(value: Any, cpp_type: str) -> str:
    """Format value as C++ literal based on cpp_type.

    | cpp_type | Formatting rule | Example |
    |----------|----------------|---------|
    | float | {value}f | 55.f, 400.0f |
    | double | {value} no suffix | 96.0 |
    | bool | true / false | true |
    | int32/int/int64 | Integer without suffix | 1500 |
    | FString/FName | TEXT("value") | TEXT("value") |
    | FText | FText::FromString("value") | FText::FromString("hello") |
    | uint8/byte | Without suffix | 255 |
    | E* (enum) | Use value directly | EFirstPersonPrimitiveType::FirstPerson |
    | Other | str(value) | Return as-is |

    Args:
        value: Python default value
        cpp_type: C++ type name

    Returns:
        C++ literal expression string
    """
    if value is None:
        return ""

    # Empty string or pure whitespace -- no valid default value (prevent output "= ;")
    if isinstance(value, str) and not value.strip():
        return ""

    # float -- 55.f format
    if cpp_type == "float":
        return _format_float_value(value)

    # double -- no suffix
    if cpp_type == "double":
        return str(float(value))

    # bool -- true/false
    if cpp_type == "bool":
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return "true" if value else "false"
        if isinstance(value, str):
            return "true" if value.lower() in ("true", "1") else "false"
        return "false"

    # Integer types -- no suffix
    if cpp_type in ("int32", "int", "int64", "uint8", "uint16", "uint32", "uint64", "byte"):
        return str(int(value))

    # FString / FName -- TEXT() wrapping
    if cpp_type in ("FString", "FName"):
        str_val = str(value)
        _validate_no_cpp_syntax(str_val)
        return f'TEXT("{_escape_cpp_string(str_val)}")'

    # FText -- FText::FromString() wrapping
    if cpp_type == "FText":
        str_val = str(value)
        _validate_no_cpp_syntax(str_val)
        return f'FText::FromString("{_escape_cpp_string(str_val)}")'

    # Enum types (UE convention: E + uppercase letter, e.g. EFirstPersonPrimitiveType) -- use value directly
    if len(cpp_type) > 1 and cpp_type[0] == "E" and cpp_type[1].isupper():
        return str(value)

    # Array / StructValue / opaque fallback -- output empty string instead of Python repr
    # These types cannot be expressed as literals in C++; skipping assignment is better than outputting invalid syntax
    if isinstance(value, (list, tuple)):
        return ""
    str_val = str(value)
    if "StructValue(" in str_val or "[" in str_val:
        return ""

    # Other types -- return string representation directly
    return str_val


def _format_fvector(x: float, y: float, z: float) -> str:
    """Format FVector literal.

    Args:
        x, y, z: 3D coordinate values

    Returns:
        FVector(x, y, z) C++ expression
    """
    return f"FVector({_format_float_value(x)}, {_format_float_value(y)}, {_format_float_value(z)})"


def _format_frotator(pitch: float, yaw: float, roll: float) -> str:
    """Format FRotator literal.

    Note: UE FRotator constructor parameter order is (pitch, yaw, roll),
    while RotatorValue storage order is (roll, pitch, yaw).

    Args:
        pitch: Pitch angle (degrees)
        yaw: Yaw angle (degrees)
        roll: Roll angle (degrees)

    Returns:
        FRotator(pitch, yaw, roll) C++ expression
    """
    return f"FRotator({_format_float_value(pitch)}, {_format_float_value(yaw)}, {_format_float_value(roll)})"


def format_cpp_transform(transforms: Dict[str, Any], component_name: str) -> List[str]:
    """Generate C++ transform assignment statements from a component's transforms dictionary.

    Rules (D-59-06):
    - Both location + rotation -> SetRelativeLocationAndRotation combined call
    - Only location -> SetRelativeLocation
    - Only rotation -> SetRelativeRotation
    - Has scale -> SetRelativeScale3D

    Args:
        transforms: Dictionary containing relative_location/relative_rotation/relative_scale
        component_name: Component variable name

    Returns:
        List of C++ statement strings (each ending with semicolon)
    """
    if not transforms:
        return []

    lines: List[str] = []
    loc = transforms.get("relative_location")
    rot = transforms.get("relative_rotation")
    scale = transforms.get("relative_scale")

    # Location + Rotation -> combined call
    if loc is not None and rot is not None:
        loc_expr = _format_fvector(loc.x, loc.y, loc.z)
        # RotatorValue storage order: (roll, pitch, yaw) -> FRotator order: (pitch, yaw, roll)
        rot_expr = _format_frotator(rot.pitch, rot.yaw, rot.roll)
        lines.append(
            f"{component_name}->SetRelativeLocationAndRotation(\n"
            f"    {loc_expr},\n"
            f"    {rot_expr}\n"
            f");"
        )
    elif loc is not None:
        loc_expr = _format_fvector(loc.x, loc.y, loc.z)
        lines.append(f"{component_name}->SetRelativeLocation({loc_expr});")

    if rot is not None and loc is None:
        rot_expr = _format_frotator(rot.pitch, rot.yaw, rot.roll)
        lines.append(f"{component_name}->SetRelativeRotation({rot_expr});")

    if scale is not None:
        scale_expr = _format_fvector(scale.x, scale.y, scale.z)
        lines.append(f"{component_name}->SetRelativeScale3D({scale_expr});")

    return lines


def format_cpp_component_init(
    component_name: str,
    cpp_type: str,
    transforms: Optional[Dict[str, Any]] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Generate complete initialization code block for a single component.

    Generates:
    1. CreateDefaultSubobject<Type>(TEXT("ComponentName"))
    2. Transform assignment statements (if any)
    3. Property assignment statements (if any)

    Args:
        component_name: Component variable name
        cpp_type: Dereferenced C++ type name (e.g. USkeletalMeshComponent)
        transforms: Transform dictionary (relative_location/relative_rotation/relative_scale)
        properties: Property dictionary (scalar property name -> (cpp_type, value))

    Returns:
        List of C++ statement strings
    """
    lines: List[str] = []

    # 1. Component creation
    lines.append(
        f'{component_name} = CreateDefaultSubobject<{cpp_type}>(TEXT("{component_name}"));'
    )

    # 2. Transform assignment
    if transforms:
        lines.extend(format_cpp_transform(transforms, component_name))

    # 3. Property assignment
    if properties:
        for prop_name, (prop_type, prop_value) in properties.items():
            cpp_value = format_cpp_default_value(prop_value, prop_type)
            if cpp_value:
                lines.append(f"{component_name}->{prop_name} = {cpp_value};")

    return lines


def format_cpp_input_action_load(variable_name: str, asset_path: str) -> str:
    """Generate LoadObject call for InputAction variable.

    D-59-06 supplement: InputAction uses LoadObject instead of CreateDefaultSubobject.

    Security validation (T-059-04): asset_path must match /Game/... pattern.

    Args:
        variable_name: Variable name
        asset_path: UE asset path (e.g. /Game/Input/Actions/IA_Jump.IA_Jump)

    Returns:
        LoadObject C++ expression string, empty string if asset_path is empty or invalid
    """
    if not asset_path:
        return ""

    # T-059-04: Validate asset path format
    if not UE_ASSET_PATH_PATTERN.match(asset_path):
        raise ValueError(
            f"Invalid asset path (must start with /Game/...): {asset_path!r}"
        )

    # Escape quotes
    safe_path = _escape_cpp_string(asset_path)
    return f'{variable_name} = LoadObject<UInputAction>(nullptr, TEXT("{safe_path}"));'
