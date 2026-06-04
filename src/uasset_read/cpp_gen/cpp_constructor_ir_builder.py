"""
构造函数 IR 构建器模块。

从 CppClassIR.properties、component 数据和 blueprint.variables 提取数据，
填充 CppClassIR.constructor 字典的 component_creations、component_assignments、
default_values 三个列表。

数据模型：
    CppComponentCreation: CreateDefaultSubobject 调用
    CppComponentAssignment: SetupAttachment 调用
    CppDefaultValue: 属性赋值（含 transform 方法调用）

构建函数：
    build_component_creations: 从 ir.properties 提取组件创建
    build_component_assignments: 从 components 数据提取 attach 关系
    build_default_values: 从 ir.properties 和 blueprint_vars 提取默认值
    build_transform_assignments: 从 component transforms 提取变换数据
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from uasset_read.cpp_gen.formatters.cpp_json_ir import CppClassIR
    from uasset_read.models.blueprint import BlueprintVariable


from uasset_read.constants import BLUEPRINT_METADATA_KEYS as _BLUEPRINT_METADATA_KEYS


def _is_blueprint_metadata(var_name: str) -> bool:
    """检查变量名是否为蓝图元数据键。"""
    return var_name in _BLUEPRINT_METADATA_KEYS


# ============================================================================
# 数据模型
# ============================================================================


@dataclass
class CppComponentCreation:
    """CreateDefaultSubobject 调用。

    表示在 C++ 构造函数中创建一个组件实例：
    ```cpp
    FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FirstPersonMesh"));
    ```

    Attributes:
        variable_name: C++ 变量名（如 "FirstPersonMesh"）
        cpp_type: 去指针的 C++ 类型（如 "USkeletalMeshComponent"）
        component_name: TEXT() 参数（如 "FirstPersonMesh"）
    """
    variable_name: str
    cpp_type: str
    component_name: str

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 兼容字典。"""
        return {
            "variable_name": self.variable_name,
            "cpp_type": self.cpp_type,
            "component_name": self.component_name,
        }


@dataclass
class CppComponentAssignment:
    """SetupAttachment 调用。

    表示在 C++ 构造函数中将子组件 attach 到父组件：
    ```cpp
    FirstPersonCameraComponent->SetupAttachment(FirstPersonMesh, TEXT("head"));
    ```

    Attributes:
        child_name: 子组件变量名
        parent_name: 父组件变量名
        socket_name: 插槽名（可为空字符串）
    """
    child_name: str
    parent_name: str
    socket_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 兼容字典。"""
        return {
            "child_name": self.child_name,
            "parent_name": self.parent_name,
            "socket_name": self.socket_name,
        }


@dataclass
class CppDefaultValue:
    """属性赋值或方法调用式赋值。

    表示在 C++ 构造函数中设置属性值或调用方法：
    - 普通赋值: `TargetArmLength = 400.0f;`
    - 方法调用: `GetCapsuleComponent()->InitCapsuleSize(55.f, 96.0f);`
    - Transform: `FirstPersonCameraComponent->SetRelativeLocationAndRotation(...);`
    - LoadObject: `IA_JumpAction = LoadObject<UInputAction>(nullptr, TEXT("/Game/..."));`

    Attributes:
        target: 赋值目标（如 "FirstPersonCameraComponent->bUsePawnControlRotation"）
        value: 格式化后的值字符串
        cpp_type: C++ 类型（如 "float", "bool", "transform"）
        is_method_call: 是否为方法调用式赋值
        method_type: 方法调用类型分类（"transform" 表示 transform 赋值，空字符串表示普通赋值）
        needs_load_object: 是否需要 LoadObject 加载（UInputAction* 等数据资产标记为 True）
    """
    target: str
    value: str
    cpp_type: str
    is_method_call: bool = False
    method_type: str = ""
    needs_load_object: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 兼容字典。"""
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
# 构建函数
# ============================================================================


def build_component_creations(ir: "CppClassIR") -> List[CppComponentCreation]:
    """从 CppClassIR.properties 中提取组件创建信息。

    遍历 ir.properties，筛选 category == "component" 的条目，
    为每个组件生成 CppComponentCreation。

    特殊处理：
    - UInputAction* 类型被跳过（它们作为数据资产存在，不使用 CreateDefaultSubobject）

    Args:
        ir: CppClassIR 实例

    Returns:
        CppComponentCreation 列表
    """
    creations: List[CppComponentCreation] = []

    for prop in ir.properties:
        if prop.category != "component":
            continue

        # D-59-06: InputAction 特殊处理 — 跳过 CreateDefaultSubobject
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
    """从组件数据中提取 attach 关系。

    遍历 components 列表（来自 extract_components 的输出），
    检查每个组件是否存在 attach_parent 字段。

    Args:
        components: 组件字典列表，每个包含 name/class/properties/transforms 键，
                    可能包含 attach_parent/attach_socket_name 字段

    Returns:
        CppComponentAssignment 列表
    """
    assignments: List[CppComponentAssignment] = []

    for comp in components:
        # 支持多种字段命名方式
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

        # 映射 Root/RootComponent -> RootComponent
        parent_name = attach_parent
        if parent_name in ("Root", "RootComponent", "root"):
            parent_name = "RootComponent"

        # 提取 socket 名称
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
    blueprint_vars: Optional[List["BlueprintVariable"]] = None,
) -> List[CppDefaultValue]:
    """从 CppClassIR.properties 和 blueprint.variables 中提取默认值。

    遍历 ir.properties 中 category == "variable" 的条目，以及可选的
    blueprint_vars 列表，生成 CppDefaultValue 条目。

    特殊处理：
    - UInputAction* 类型：标记 needs_load_object=True（需要 LoadObject 加载）
    - 非 InputAction 变量但 default_value 为 None：跳过
    - T-059-02: 过滤 value 中的潜在注入字符（;, {}, //）

    Args:
        ir: CppClassIR 实例
        blueprint_vars: 可选的 BlueprintVariable 列表

    Returns:
        CppDefaultValue 列表
    """
    defaults: List[CppDefaultValue] = []

    # 从 ir.properties 提取变量默认值
    for prop in ir.properties:
        if prop.category != "variable":
            continue

        # InputAction 特殊处理
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

        # 普通变量 — 跳过无默认值的
        if prop.default_value is None:
            continue

        value_str = _sanitize_value(str(prop.default_value), prop.cpp_type)
        defaults.append(CppDefaultValue(
            target=prop.name,
            value=value_str,
            cpp_type=prop.cpp_type,
        ))

    # 从 blueprint_vars 补充提取
    if blueprint_vars:
        for var in blueprint_vars:
            if var.is_component:
                continue
            if var.default_value is None:
                continue
            if _is_blueprint_metadata(var.var_name):
                continue

            # 跳过已经在 ir.properties 中处理过的变量
            already_processed = any(
                d.target == var.var_name for d in defaults
            )
            if already_processed:
                continue

            cpp_type = _blueprint_var_type_to_cpp(var)
            value_str = _sanitize_value(str(var.default_value), cpp_type)
            defaults.append(CppDefaultValue(
                target=var.var_name,
                value=value_str,
                cpp_type=cpp_type,
            ))

    logger.info(f"Built {len(defaults)} default values")
    return defaults


def build_transform_assignments(
    ir: "CppClassIR",
    components: List[Dict[str, Any]],
) -> List[CppDefaultValue]:
    """从组件 transforms 数据提取变换赋值到 IR。

    遍历 components 列表，检查每个组件的 transforms 字典是否包含
    relative_location 或 relative_rotation 等键。如果存在，
    创建 CppDefaultValue 条目，标记 is_method_call=True, method_type="transform"。

    Blocker 2 fix: transform 数据流入 IR default_values。

    Args:
        ir: CppClassIR 实例
        components: 组件字典列表

    Returns:
        CppDefaultValue 列表（is_method_call=True, method_type="transform"）
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
# 辅助函数
# ============================================================================


def _sanitize_value(value: str, cpp_type: str) -> str:
    """T-059-02: 清理值字符串，防止代码注入。

    拒绝包含 ;, {, }, // 的值（可能用于注入 C++ 代码）。
    对于检测到的危险值，返回清理后的版本（移除危险字符）并记录警告。

    Args:
        value: 原始值字符串
        cpp_type: C++ 类型（用于上下文）

    Returns:
        清理后的值字符串
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
        # 移除危险字符
        cleaned = value
        for ch in dangerous_chars:
            cleaned = cleaned.replace(ch, "")
        for pat in dangerous_patterns:
            cleaned = cleaned.replace(pat, "")
        return cleaned.strip()

    return value


def _blueprint_var_type_to_cpp(var: "BlueprintVariable") -> str:
    """从 BlueprintVariable 的 var_type 推导 C++ 类型。

    Args:
        var: BlueprintVariable 实例

    Returns:
        C++ 类型字符串
    """
    from uasset_read.cpp_gen.cpp_type_mapper import ue_path_to_cpp_type

    var_type = var.var_type
    category = var_type.pin_category if var_type else ""
    subcategory = var_type.pin_subcategory if var_type else ""

    # 基本类型映射
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

    # object 类型
    if category in ("object", "ObjectProperty", "SoftObjectProperty"):
        if subcategory:
            cpp_type = ue_path_to_cpp_type(subcategory)
            if not cpp_type.endswith("*"):
                cpp_type = f"{cpp_type}*"
            return cpp_type
        return "UObject*"

    # struct 类型
    if category in ("struct", "StructProperty"):
        if subcategory:
            cpp_type = ue_path_to_cpp_type(subcategory)
            return cpp_type
        return "FName"

    # 回退
    if category:
        return ue_path_to_cpp_type(category)
    return "FString"


# ============================================================================
# 导出列表
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
