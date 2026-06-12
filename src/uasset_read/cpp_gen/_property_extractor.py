"""C++ 类骨架提取 — 属性提取。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any

from uasset_read.cpp_gen.formatters import CppProperty
from uasset_read.cpp_gen.cpp_uproperty_mapper import cpf_flags_to_uproperty_marks
from uasset_read.cpp_gen.cpp_type_mapper import ue_path_to_cpp_type
from uasset_read.cpp_gen.sanitizer import sanitize_identifier
from uasset_read.cpp_gen._class_extractor import _clean_component_name, _is_blueprint_metadata

if TYPE_CHECKING:
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.models.blueprint import BlueprintMetadata, BlueprintVariable
    from uasset_read.models.core import FEdGraphPinType

logger = logging.getLogger(__name__)


# ============================================================================
# 组件属性提取
# ============================================================================

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
            # P1 改进：清理组件名称
            clean_name = _clean_component_name(comp_name)

            # 补全短名称为完整路径（如 "ArrowComponent" → "/Script/Engine.ArrowComponent"）
            comp_path = comp_class
            if not comp_path.startswith("/Script/"):
                # 假设是 Engine 类型，补全路径
                comp_path = f"/Script/Engine.{comp_class}"

            # 构建组件类型（指针）
            cpp_type = ue_path_to_cpp_type(comp_path)
            if not cpp_type.endswith("*"):
                cpp_type = f"{cpp_type}*"

            # SCS 组件默认标记
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


def _create_component_property(var: "BlueprintVariable") -> CppProperty:
    """从 BlueprintVariable 创建组件 CppProperty。

    P1 改进：使用 _clean_component_name 清理组件名称。

    Args:
        var: BlueprintVariable（is_component=True）

    Returns:
        CppProperty
    """
    # P1 改进：清理组件名称
    clean_name = _clean_component_name(var.var_name)

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
        name=clean_name,
        uproperty_marks=marks,
        category="component",
        default_value=None,  # 组件无默认值
        cpp_comment=f"UE type: {ue_type}",
    )


# ============================================================================
# 变量属性提取
# ============================================================================

def _extract_variable_properties(blueprint: "BlueprintMetadata") -> List[CppProperty]:
    """提取变量属性。

    从 blueprint.variables 中筛选 is_component=False 的变量。
    P0 改进：过滤蓝图内部元数据属性。

    Args:
        blueprint: BlueprintMetadata

    Returns:
        CppProperty 列表（category="variable"）
    """
    properties: List[CppProperty] = []

    for var in blueprint.variables:
        if not var.is_component:
            # P0 改进：过滤蓝图元数据
            if _is_blueprint_metadata(var.var_name):
                continue
            prop = _create_variable_property(var)
            properties.append(prop)

    return properties


def _extract_input_action_properties(graphs: List["UEdGraph"]) -> List[CppProperty]:
    """从图节点提取输入动作变量。

    P2 改进：从 K2Node_EnhancedInputAction 节点提取输入动作引用，
    生成 UInputAction* 成员变量。

    Args:
        graphs: 图列表

    Returns:
        CppProperty 列表（category="input"）
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

            # 获取输入动作引用
            action_path = nd.get("input_action_path", "")
            action_short_name = nd.get("input_action_short_name", "")

            if not action_path or action_path == "None":
                continue

            # 去重（同一个输入动作可能被多个节点引用）
            if action_path in seen_actions:
                continue
            seen_actions.add(action_path)

            # 生成变量名（使用短名称）
            var_name = action_short_name if action_short_name else action_path

            # 构建属性
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
        name=sanitize_identifier(var.var_name),
        uproperty_marks=marks,
        category="variable",
        default_value=var.default_value,
        cpp_comment=f"UE type: {ue_type}",
    )


# ============================================================================
# 类型映射辅助
# ============================================================================

def _build_ue_type_from_pin_type(pin_type: "FEdGraphPinType") -> str:
    """从 FEdGraphPinType 构建 UE 类型路径。

    Args:
        pin_type: FEdGraphPinType

    Returns:
        UE 类型路径字符串
    """
    category = pin_type.pin_category
    subcategory = pin_type.pin_subcategory

    # 属性类型（Property）→ 映射到对应的 UE 基本类型
    if category in ("IntProperty",):
        return "int32"
    if category in ("FloatProperty", "DoubleProperty"):
        return "float" if category == "FloatProperty" else "double"
    if category in ("BoolProperty",):
        return "bool"
    if category in ("ObjectProperty", "SoftObjectProperty"):
        # ObjectProperty 总是指针类型
        cpp_type = subcategory if subcategory else "UObject"
        if not cpp_type.endswith("*"):
            cpp_type = f"{cpp_type}*"
        return cpp_type
    if category in ("ArrayProperty", "SetProperty", "MapProperty"):
        # 对于集合类型，返回元素类型（从 pin_type 中提取）
        # 如果没有 subcategory，返回基本类型
        return subcategory if subcategory else "FString"
    if category in ("StrProperty", "NameProperty", "TextProperty"):
        cpp_type_map = {
            "StrProperty": "FString",
            "NameProperty": "FName",
            "TextProperty": "FText",
        }
        return cpp_type_map.get(category, category)

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
    if category in ("struct", "StructProperty"):
        if subcategory:
            if subcategory.startswith("/Script/"):
                return subcategory
            # 常见结构体补全路径
            common_structs = ("Vector", "Rotator", "Transform", "Vector2D",
                              "LinearColor", "Color", "Guid", "Quat", "Box")
            if subcategory in common_structs:
                return f"/Script/CoreUObject.{subcategory}"
            return f"/Script/CoreUObject.{subcategory}"
        # StructProperty 无 subcategory — 使用通用 FStruct 占位
        return "FStruct"

    # 其他类型返回 category
    return category


def _extract_cpp_type_from_pin(pin: "UEdGraphPin") -> Optional[str]:
    """将单个引脚转换为 C++ 类型字符串。

    返回 None 表示应跳过（exec/delegate 引脚）。
    """
    if pin.pin_type is None:
        return None
    pt = pin.pin_type
    if pt.pin_category in ("exec", "delegate"):
        return None

    # 获取基础类型
    if pt.pin_category in ("object", "struct"):
        # 尝试解析 pin_subcategory_object
        if pt.pin_subcategory_object and isinstance(pt.pin_subcategory_object, int):
            # 有 linker 时可解析，此处用 pin_subcategory 作为回退
            raw_path = pt.pin_subcategory
        else:
            raw_path = pt.pin_subcategory
        if not raw_path:
            raw_path = pt.pin_category
    else:
        raw_path = pt.pin_subcategory or pt.pin_category

    cpp_type = ue_path_to_cpp_type(raw_path)

    # 对象类型加指针
    if pt.pin_category == "object" and not cpp_type.endswith("*"):
        cpp_type = f"{cpp_type}*"

    # 方向修饰符
    if pt.is_reference and pt.is_const:
        cpp_type = f"const {cpp_type}&"
    elif pt.is_reference:
        cpp_type = f"{cpp_type}&"

    return cpp_type
