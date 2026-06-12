"""C++ 默认值格式化器 — 将 Python 值转换为类型正确的 C++ 字面量。

为构造函数生成器提供类型安全的值格式化工具。

安全缓解（威胁模型 T-059-03, T-059-04）：
- 字符串值中引号转义
- 拒绝包含 C++ 语法令牌（;, {, }, //）的值
- InputAction asset_path 验证 /Game/... 模式
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from uasset_read.models.transforms import RotatorValue, ScaleValue, VectorValue

# ============================================================================
# 安全常量（T-059-03）
# ============================================================================

# 拒绝包含这些 C++ 语法令牌的值
CPP_SYNTAX_TOKENS = [';', '{', '}', '//']

# UE 资源路径模式（T-059-04）
UE_ASSET_PATH_PATTERN = re.compile(r'^/Game/')


def _escape_cpp_string(value: str) -> str:
    """转义字符串值以防止 C++ 注入（T-059-03）。

    Args:
        value: 原始字符串值

    Returns:
        转义后的字符串值
    """
    # 转义反斜杠（必须先处理）
    value = value.replace('\\', '\\\\')
    # 转义双引号
    value = value.replace('"', '\\"')
    # 转义控制字符
    value = value.replace('\n', '\\n')
    value = value.replace('\r', '\\r')
    value = value.replace('\t', '\\t')
    return value


def _validate_no_cpp_syntax(value: str) -> str:
    """验证字符串值不包含 C++ 语法令牌（T-059-03）。

    Args:
        value: 要验证的字符串值

    Returns:
        原始值（如果安全）

    Raises:
        ValueError: 如果值包含 C++ 语法令牌
    """
    for token in CPP_SYNTAX_TOKENS:
        if token in value:
            raise ValueError(
                f"Value contains C++ syntax token '{token}': {value!r}"
            )
    return value


def _format_float_value(value: float) -> str:
    """格式化 float 值为 C++ 字面量（55.f 格式）。

    - 整数值：`55.f`
    - 有小数部分：`400.12f`

    Args:
        value: 浮点数值

    Returns:
        C++ float 字面量字符串
    """
    fval = float(value)
    if fval == int(fval):
        return f"{int(fval)}.f"
    return f"{fval}f"


def format_cpp_default_value(value: Any, cpp_type: str) -> str:
    """根据 cpp_type 将 value 格式化为 C++ 字面量。

    | cpp_type | 格式化规则 | 示例 |
    |----------|-----------|------|
    | float | {value}f | 55.f, 400.0f |
    | double | {value} 无后缀 | 96.0 |
    | bool | true / false | true |
    | int32/int/int64 | 无后缀整数 | 1500 |
    | FString/FName | TEXT("value") | TEXT("value") |
    | FText | FText::FromString("value") | FText::FromString("hello") |
    | uint8/byte | 无后缀 | 255 |
    | E* (枚举) | 直接使用值 | EFirstPersonPrimitiveType::FirstPerson |
    | 其他 | str(value) | 直接返回 |

    Args:
        value: Python 默认值
        cpp_type: C++ 类型名

    Returns:
        C++ 字面量表达式字符串
    """
    if value is None:
        return ""

    # 空字符串或纯空白 — 无有效默认值（防止输出 "= ;"）
    if isinstance(value, str) and not value.strip():
        return ""

    # float — 55.f 格式
    if cpp_type == "float":
        return _format_float_value(value)

    # double — 无后缀
    if cpp_type == "double":
        return str(float(value))

    # bool — true/false
    if cpp_type == "bool":
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return "true" if value else "false"
        if isinstance(value, str):
            return "true" if value.lower() in ("true", "1") else "false"
        return "false"

    # 整数类型 — 无后缀
    if cpp_type in ("int32", "int", "int64", "uint8", "uint16", "uint32", "uint64", "byte"):
        return str(int(value))

    # FString / FName — TEXT() 包装
    if cpp_type in ("FString", "FName"):
        str_val = str(value)
        _validate_no_cpp_syntax(str_val)
        return f'TEXT("{_escape_cpp_string(str_val)}")'

    # FText — FText::FromString() 包装
    if cpp_type == "FText":
        str_val = str(value)
        _validate_no_cpp_syntax(str_val)
        return f'FText::FromString("{_escape_cpp_string(str_val)}")'

    # 枚举类型（以 E 开头）— 直接使用值
    if cpp_type.startswith("E"):
        return str(value)

    # 数组 / StructValue / opaque fallback — 输出空字符串而非 Python repr
    # 这些类型无法在 C++ 中用字面量表达，跳过赋值比输出非法语法更好
    if isinstance(value, (list, tuple)):
        return ""
    str_val = str(value)
    if "StructValue(" in str_val or "[" in str_val:
        return ""

    # 其他类型 — 直接返回字符串表示
    return str_val


def _format_fvector(x: float, y: float, z: float) -> str:
    """格式化 FVector 字面量。

    Args:
        x, y, z: 三维坐标值

    Returns:
        FVector(x, y, z) C++ 表达式
    """
    return f"FVector({_format_float_value(x)}, {_format_float_value(y)}, {_format_float_value(z)})"


def _format_frotator(pitch: float, yaw: float, roll: float) -> str:
    """格式化 FRotator 字面量。

    注意：UE FRotator 构造函数参数顺序为 (pitch, yaw, roll)，
    而 RotatorValue 存储顺序为 (roll, pitch, yaw)。

    Args:
        pitch: 俯仰角（度）
        yaw: 偏航角（度）
        roll: 翻滚角（度）

    Returns:
        FRotator(pitch, yaw, roll) C++ 表达式
    """
    return f"FRotator({_format_float_value(pitch)}, {_format_float_value(yaw)}, {_format_float_value(roll)})"


def format_cpp_transform(transforms: Dict[str, Any], component_name: str) -> List[str]:
    """从组件的 transforms 字典生成 C++ transform 赋值语句。

    规则（D-59-06）：
    - 同时有 location + rotation → SetRelativeLocationAndRotation 组合调用
    - 只有 location → SetRelativeLocation
    - 只有 rotation → SetRelativeRotation
    - 有 scale → SetRelativeScale3D

    Args:
        transforms: 包含 relative_location/relative_rotation/relative_scale 的字典
        component_name: 组件变量名

    Returns:
        C++ 语句字符串列表（每条末尾带分号）
    """
    if not transforms:
        return []

    lines: List[str] = []
    loc = transforms.get("relative_location")
    rot = transforms.get("relative_rotation")
    scale = transforms.get("relative_scale")

    # Location + Rotation → 组合调用
    if loc is not None and rot is not None:
        loc_expr = _format_fvector(loc.x, loc.y, loc.z)
        # RotatorValue 存储顺序: (roll, pitch, yaw) → FRotator 顺序: (pitch, yaw, roll)
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
    """为单个组件生成完整的初始化代码块。

    生成：
    1. CreateDefaultSubobject<Type>(TEXT("ComponentName"))
    2. Transform 赋值语句（如果有）
    3. 属性赋值语句（如果有）

    Args:
        component_name: 组件变量名
        cpp_type: 去指针的 C++ 类型名（如 USkeletalMeshComponent）
        transforms: 变换字典（relative_location/relative_rotation/relative_scale）
        properties: 属性字典（标量属性名 → (cpp_type, value)）

    Returns:
        C++ 语句字符串列表
    """
    lines: List[str] = []

    # 1. 组件创建
    lines.append(
        f'{component_name} = CreateDefaultSubobject<{cpp_type}>(TEXT("{component_name}"));'
    )

    # 2. Transform 赋值
    if transforms:
        lines.extend(format_cpp_transform(transforms, component_name))

    # 3. 属性赋值
    if properties:
        for prop_name, (prop_type, prop_value) in properties.items():
            cpp_value = format_cpp_default_value(prop_value, prop_type)
            if cpp_value:
                lines.append(f"{component_name}->{prop_name} = {cpp_value};")

    return lines


def format_cpp_input_action_load(variable_name: str, asset_path: str) -> str:
    """为 InputAction 变量生成 LoadObject 调用。

    D-59-06 补充：InputAction 使用 LoadObject 而非 CreateDefaultSubobject。

    安全验证（T-059-04）：asset_path 必须匹配 /Game/... 模式。

    Args:
        variable_name: 变量名
        asset_path: UE 资源路径（如 /Game/Input/Actions/IA_Jump.IA_Jump）

    Returns:
        LoadObject C++ 表达式字符串，如果 asset_path 为空或无效则返回空字符串
    """
    if not asset_path:
        return ""

    # T-059-04: 验证资产路径格式
    if not UE_ASSET_PATH_PATTERN.match(asset_path):
        raise ValueError(
            f"Invalid asset path (must start with /Game/...): {asset_path!r}"
        )

    # 转义引号
    safe_path = _escape_cpp_string(asset_path)
    return f'{variable_name} = LoadObject<UInputAction>(nullptr, TEXT("{safe_path}"));'
