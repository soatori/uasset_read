"""
C++ 类骨架提取模块 — extract_cpp_class_skeleton()。

Per D-02: 沿 ClassParent 追溯继承链。
Per D-03: 使用 ue_path_to_cpp_type 进行类型映射。
Per D-04: 使用 cpf_flags_to_uproperty_marks 获取 UPROPERTY 标记。
Per D-05: 构建完整的 header_meta。
Per D-06: 返回 CppClassIR，methods/constructor 留空。

导出：
    extract_cpp_class_skeleton: LinkerParseResult → CppClassIR 提取函数
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any

from uasset_read.cpp_gen.formatters import (
    CppClassIR,
    CppProperty,
    CppHeaderMeta,
)
from uasset_read.cpp_gen.cpp_type_mapper import (
    ue_path_to_cpp_type,
    ue_package_path_to_cpp_class,
)
from uasset_read.cpp_gen.cpp_uproperty_mapper import (
    cpf_flags_to_uproperty_marks,
)
from uasset_read.constants import CPF_InstancedReference

if TYPE_CHECKING:
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.models.blueprint import BlueprintMetadata, BlueprintVariable
    from uasset_read.models.core import FEdGraphPinType

logger = logging.getLogger(__name__)

# ============================================================================
# 继承链深度限制（T-056-03）
# ============================================================================

MAX_INHERITANCE_DEPTH = 50  # 防止无限循环


# ============================================================================
# 核心提取函数
# ============================================================================

def extract_cpp_class_skeleton(result: "LinkerParseResult") -> CppClassIR:
    """从 LinkerParseResult 提取 C++ 类骨架。

    Per D-02: 从 BlueprintMetadata.parent_class 追溯继承链。
    Per D-03: 将 UE 类型映射为 C++ 类型名。
    Per D-04: 将 CPF 标志转换为 UPROPERTY 标记。
    Per D-05: 构建 header_meta（includes + generated_include）。
    Per D-06: 返回 CppClassIR，properties 填充，methods/constructor 留空。

    Args:
        result: LinkerParseResult（来自 parse_uasset_with_linker）

    Returns:
        CppClassIR: C++ 类骨架中间表示

    Raises:
        ValueError: 如果 result.blueprint 为 None 或不是蓝图
    """
    # 验证输入
    if result.blueprint is None:
        raise ValueError("LinkerParseResult.blueprint is None — cannot extract skeleton")
    if not result.blueprint.is_blueprint:
        raise ValueError("LinkerParseResult.blueprint.is_blueprint is False — not a blueprint")

    blueprint = result.blueprint

    # 1. 提取类名
    class_name = _extract_class_name(result)

    # 2. 解析继承链（Per D-02）
    parent_class = _resolve_parent_class(blueprint, result.linker)

    # 3. 提取组件属性
    properties: List[CppProperty] = []
    properties.extend(_extract_component_properties(blueprint, result.components))

    # 4. 提取变量属性
    properties.extend(_extract_variable_properties(blueprint))

    # 5. 构建 header_meta（Per D-05）
    header_meta = CppHeaderMeta.build_from_parent(parent_class, class_name)

    # 6. 构建并返回 CppClassIR（Per D-06）
    return CppClassIR(
        name=class_name,
        parent_class=parent_class,
        header_meta=header_meta,
        properties=properties,
        methods=[],  # Phase 57 填充
        constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [],
        },  # Phase 59 填充
    )


# ============================================================================
# 辅助函数
# ============================================================================

def _extract_class_name(result: "LinkerParseResult") -> str:
    """提取 C++ 类名。

    根据蓝图名称和父类类型确定 C++ 前缀：
    - Actor 派生 → A 前缀
    - Component 派生 → U 前缀
    - UObject 派生 → U 前缀
    - 其他 → U 前缀（默认）

    Args:
        result: LinkerParseResult

    Returns:
        C++ 类名（带前缀）
    """
    # 从 summary.package_name 或 name_map[0] 获取名称
    raw_name = ""
    if result.summary and hasattr(result.summary, 'package_name'):
        raw_name = result.summary.package_name
    elif result.name_map and len(result.name_map) > 0:
        raw_name = result.name_map[0]

    if not raw_name:
        logger.warning("Could not determine class name from result")
        return "UUnknownClass"

    # 确定前缀（根据父类类型）
    parent_class_path = result.blueprint.parent_class or ""
    parent_cpp = ue_package_path_to_cpp_class(parent_class_path)

    # T-056-04: 清理名称中的非法字符
    import re
    clean_name = re.sub(r'[^A-Za-z0-9_]', '_', raw_name)

    # 确定前缀
    prefix = "U"  # 默认 UObject 前缀
    if parent_cpp.startswith("A"):
        prefix = "A"  # Actor 前缀
    elif parent_cpp.startswith("U") and "Component" in parent_cpp:
        prefix = "U"  # Component 前缀（已经是 U）

    # 如果名称已有前缀，不重复添加
    if clean_name.startswith(('A', 'U', 'F', 'E', 'I')):
        return clean_name

    return f"{prefix}{clean_name}"


def _resolve_parent_class(
    blueprint: "BlueprintMetadata",
    linker: Optional[Any]
) -> str:
    """解析父类名。

    Per D-02: 从 blueprint.parent_class 提取并转换为 C++ 类名。
    未来支持通过 linker 深度追溯继承链（当前仅直接父类）。

    Args:
        blueprint: BlueprintMetadata
        linker: PackageLinker（可选，用于深度追溯）

    Returns:
        C++ 父类名
    """
    parent_path = blueprint.parent_class
    if not parent_path:
        logger.warning("BlueprintMetadata.parent_class is None — using UObject as default")
        return "UObject"

    return ue_package_path_to_cpp_class(parent_path)


def _extract_component_properties(
    blueprint: "BlueprintMetadata",
    components: List[Dict]
) -> List[CppProperty]:
    """提取组件属性。

    从 blueprint.variables 中筛选 is_component=True 的变量，
    以及 result.components 列表中的 SCS 组件。

    Args:
        blueprint: BlueprintMetadata
        components: result.components 列表

    Returns:
        CppProperty 列表（category="component"）
    """
    properties: List[CppProperty] = []

    # 从 blueprint.variables 提取组件
    for var in blueprint.variables:
        if var.is_component:
            prop = _create_component_property(var)
            properties.append(prop)

    # 从 result.components 提取 SCS 组件（如果有）
    for comp in components:
        comp_name = comp.get("name", "")
        comp_class = comp.get("class", "")

        if comp_name and comp_class:
            # 构建组件类型（指针）
            cpp_type = ue_path_to_cpp_type(comp_class)
            if not cpp_type.endswith("*"):
                cpp_type = f"{cpp_type}*"

            # SCS 组件默认标记
            marks = ["VisibleAnywhere", "BlueprintReadOnly", "Instanced"]

            prop = CppProperty(
                cpp_type=cpp_type,
                name=comp_name,
                uproperty_marks=marks,
                category="component",
                default_value=None,
            )
            properties.append(prop)

    return properties


def _create_component_property(var: "BlueprintVariable") -> CppProperty:
    """从 BlueprintVariable 创建组件 CppProperty。

    Args:
        var: BlueprintVariable（is_component=True）

    Returns:
        CppProperty
    """
    # 从 var_type 提取类型路径
    var_type = var.var_type
    ue_type = ""

    if var_type.pin_category == "object":
        # object 类型：pin_subcategory 是类名
        ue_type = var_type.pin_subcategory
        if not ue_type.startswith("/Script/"):
            # 补全路径
            ue_type = f"/Script/Engine.{ue_type}"
    else:
        # 其他类型直接使用 category
        ue_type = var_type.pin_category

    # 转换为 C++ 类型（组件是指针）
    cpp_type = ue_path_to_cpp_type(ue_type)
    if not cpp_type.endswith("*"):
        cpp_type = f"{cpp_type}*"

    # 获取 UPROPERTY 标记（组件模式）
    marks = cpf_flags_to_uproperty_marks(var.property_flags, is_component=True)

    return CppProperty(
        cpp_type=cpp_type,
        name=var.var_name,
        uproperty_marks=marks,
        category="component",
        default_value=None,  # 组件无默认值
        cpp_comment=f"UE type: {ue_type}",
    )


def _extract_variable_properties(blueprint: "BlueprintMetadata") -> List[CppProperty]:
    """提取变量属性。

    从 blueprint.variables 中筛选 is_component=False 的变量。

    Args:
        blueprint: BlueprintMetadata

    Returns:
        CppProperty 列表（category="variable"）
    """
    properties: List[CppProperty] = []

    for var in blueprint.variables:
        if not var.is_component:
            prop = _create_variable_property(var)
            properties.append(prop)

    return properties


def _create_variable_property(var: "BlueprintVariable") -> CppProperty:
    """从 BlueprintVariable 创建变量 CppProperty。

    Args:
        var: BlueprintVariable（is_component=False）

    Returns:
        CppProperty
    """
    var_type = var.var_type

    # 构建 UE 类型路径
    ue_type = _build_ue_type_from_pin_type(var_type)

    # 转换为 C++ 类型
    cpp_type = ue_path_to_cpp_type(ue_type)

    # 获取 UPROPERTY 标记（变量模式）
    marks = cpf_flags_to_uproperty_marks(var.property_flags, is_component=False)

    return CppProperty(
        cpp_type=cpp_type,
        name=var.var_name,
        uproperty_marks=marks,
        category="variable",
        default_value=var.default_value,
        cpp_comment=f"UE type: {ue_type}",
    )


def _build_ue_type_from_pin_type(pin_type: "FEdGraphPinType") -> str:
    """从 FEdGraphPinType 构建 UE 类型路径。

    Args:
        pin_type: FEdGraphPinType

    Returns:
        UE 类型路径字符串
    """
    category = pin_type.pin_category
    subcategory = pin_type.pin_subcategory

    # 基本类型直接返回
    if category in ("float", "double", "bool", "int", "int32", "int64",
                     "byte", "string", "name", "text"):
        return category

    # object 类型：subcategory 是类名
    if category == "object":
        if subcategory:
            if subcategory.startswith("/Script/"):
                return subcategory
            # 补全路径
            return f"/Script/Engine.{subcategory}"
        return "UObject"  # 未知 object 类型

    # struct 类型：subcategory 是结构名
    if category == "struct":
        if subcategory:
            if subcategory.startswith("/Script/"):
                return subcategory
            # 常见结构体补全路径
            common_structs = ("Vector", "Rotator", "Transform", "Vector2D",
                              "LinearColor", "Color", "Guid", "Quat", "Box")
            if subcategory in common_structs:
                return f"/Script/CoreUObject.{subcategory}"
            return f"/Script/CoreUObject.{subcategory}"
        return "/Script/CoreUObject.Struct"

    # 其他类型返回 category
    return category


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "extract_cpp_class_skeleton",
]