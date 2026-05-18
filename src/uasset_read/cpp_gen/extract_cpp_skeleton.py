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
# Phase 57: 函数签名映射
# ============================================================================

# --- 辅助函数（Plan 02） ---

def _sanitize_identifier(name: str) -> str:
    """将 UE 引脚名转换为有效 C++ 标识符。

    "Left / Right" → "LeftRight"
    "Primary Thumbstick" → "PrimaryThumbstick"
    "2DValue" → "_2DValue"
    """
    if not name:
        return "unnamed"
    cleaned = re.sub(r'[^A-Za-z0-9_]', '', name)
    if cleaned and cleaned[0].isdigit():
        cleaned = '_' + cleaned
    return cleaned if cleaned else "unnamed"


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


def _extract_parameters_from_pins(
    pins: List["UEdGraphPin"],
    is_event: bool = False
) -> List[CppCallParameter]:
    """从引脚列表提取函数参数。"""
    params: List[CppCallParameter] = []
    for pin in pins:
        if pin.pin_type is None:
            continue
        pt = pin.pin_type
        # 跳过 exec / delegate
        if pt.pin_category in ("exec", "delegate"):
            continue
        # 跳过隐藏引脚
        if pin.hidden:
            continue
        # 事件节点跳过 OutputDelegate 和 then
        if is_event and pin.pin_name in ("OutputDelegate", "then"):
            continue

        cpp_type = _extract_cpp_type_from_pin(pin)
        if cpp_type is None:
            continue

        params.append(CppCallParameter(
            name=_sanitize_identifier(pin.pin_name),
            cpp_type=cpp_type,
            direction="input" if pin.direction == 0 else "output",
        ))
    return params


def _infer_ufunction_specifiers(
    pins: List["UEdGraphPin"],
    node_class_name: str,
    is_override: bool
) -> List[str]:
    """推断 UFUNCTION 修饰符（D-57-03）。"""
    if is_override:
        return []
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
    """从 K2Node_FunctionEntry 构建 CppMethodIR。"""
    if fe_node.function_reference is None:
        return None
    func_name = fe_node.function_reference.member_name
    if not func_name or func_name == "None":
        return None

    # 双源交叉验证（D-57-01）
    bp_func = blueprint_functions.get(func_name)
    if bp_func:
        return_type = bp_func.return_type or "void"
        parameters = [
            CppCallParameter(
                name=_sanitize_identifier(p.name),
                cpp_type=ue_path_to_cpp_type(p.param_type),
                direction="input" if p.is_input else "output",
            )
            for p in bp_func.parameters
        ]
    else:
        # 从引脚回退
        parameters = _extract_parameters_from_pins(fe_node.pins)
        return_type = "void"

    specifiers = _infer_ufunction_specifiers(fe_node.pins, "K2Node_FunctionEntry", is_override=False)

    return CppMethodIR(
        cpp_name=_sanitize_identifier(func_name),
        return_type=return_type,
        parameters=parameters,
        ufunction_specifiers=specifiers,
        is_override=False,
        source_node_type="K2Node_FunctionEntry",
    )


def _build_cpp_method_from_event(event_node: "K2NodeEvent") -> CppMethodIR:
    """从 K2Node_Event 构建 CppMethodIR（is_override=True）。"""
    if event_node.event_reference is None:
        return None
    event_name = event_node.event_reference.member_name
    if not event_name or event_name == "None":
        return None

    parameters = _extract_parameters_from_pins(event_node.pins, is_event=True)

    return CppMethodIR(
        cpp_name=_sanitize_identifier(event_name),
        return_type="void",
        parameters=parameters,
        ufunction_specifiers=[],
        is_override=True,
        source_node_type="K2Node_Event",
    )


# --- 主入口（Plan 02） ---

def extract_cpp_functions(
    graphs: List["UEdGraph"],
    blueprint_functions: Optional[List] = None,
    linker: Optional[Any] = None,
) -> List[CppMethodIR]:
    """从函数图节点提取 C++ 方法声明。

    遍历所有图，提取 K2Node_FunctionEntry 和 K2Node_Event(b_override_function=True)。
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
                if getattr(node, 'b_override_function', False):
                    method = _build_cpp_method_from_event(node)
                    if method:
                        methods.append(method)
    return methods


# --- 调用语句提取（Plan 03） ---

def _derive_call_target(
    pins: List["UEdGraphPin"],
    b_self_context: bool
) -> Tuple[str, str]:
    """推导调用目标。

    b_self_context=True → ("this", "this")
    b_self_context=False → 从 self 引脚推导类型
    """
    if b_self_context:
        return ("this", "this")

    # 查找 self 引脚
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
    """从 K2Node_CallFunction 节点提取 C++ 调用语句参考。"""
    statements: List[CppCallStatement] = []
    for graph in graphs:
        for node in graph.nodes:
            if node.class_name != "K2Node_CallFunction":
                continue

            # 获取 function_reference
            func_ref = getattr(node, 'function_reference', None)
            if func_ref is None:
                continue
            member_name = getattr(func_ref, 'member_name', None)
            if not member_name or member_name == "None":
                continue

            b_self_context = getattr(func_ref, 'b_self_context', True)
            target, target_type = _derive_call_target(node.pins, b_self_context)

            # 提取参数（跳过 exec/then/self）
            args = []
            for pin in node.pins:
                if pin.pin_type and pin.pin_type.pin_category == "exec":
                    continue
                if pin.pin_name in ("self", "then"):
                    continue
                args.append(_sanitize_identifier(pin.pin_name))

            statements.append(CppCallStatement(
                method_name=member_name,
                target=target,
                target_type=target_type,
                args=args,
                is_self_context=b_self_context,
            ))
    return statements


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "extract_cpp_class_skeleton",
    # Phase 57
    "extract_cpp_functions",
    "extract_cpp_call_statements",
    "_sanitize_identifier",
    "_derive_call_target",
]