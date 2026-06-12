"""
C++ 类骨架提取模块 — extract_cpp_class_skeleton()。

Per D-02: 沿 ClassParent 追溯继承链。
Per D-03: 使用 ue_path_to_cpp_type 进行类型映射。
Per D-04: 使用 cpf_flags_to_uproperty_marks 获取 UPROPERTY 标记。
Per D-05: 构建完整的 header_meta。
从图节点提取方法声明填充 methods。
从 decompiled_functions 注入函数体到 body_text。

导出：
    extract_cpp_class_skeleton: LinkerParseResult → CppClassIR 提取函数
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Tuple

from uasset_read.cpp_gen.formatters import (
    CppClassIR,
    CppProperty,
    CppHeaderMeta,
    CppMethodIR,
    CppCallStatement,
)
from uasset_read.cpp_gen.cpp_type_mapper import ue_path_to_cpp_type
from uasset_read.cpp_gen.cpp_constructor_ir_builder import (
    build_component_creations,
    build_component_assignments,
    build_default_values,
    build_transform_assignments,
)
from uasset_read.cpp_gen.cpp_constructor_formatter import format_cpp_constructor
from uasset_read.cpp_gen.sanitizer import sanitize_identifier as _sanitize_identifier

# 从拆分模块导入
from uasset_read.cpp_gen._class_extractor import (
    _extract_class_name, _resolve_parent_class,
)
from uasset_read.cpp_gen._property_extractor import (
    _extract_component_properties, _extract_variable_properties,
    _extract_input_action_properties,
)
from uasset_read.cpp_gen._method_extractor import (
    _build_cpp_method_from_entry, _build_cpp_method_from_event,
    _backfill_missing_methods, _inject_function_bodies,
)

if TYPE_CHECKING:
    from uasset_read.link.result import LinkerParseResult

logger = logging.getLogger(__name__)


# ============================================================================
# 核心提取函数
# ============================================================================

def extract_cpp_class_skeleton(result: "LinkerParseResult") -> CppClassIR:
    """从 LinkerParseResult 提取 C++ 类骨架。

    Per D-02: 从 BlueprintMetadata.parent_class 追溯继承链。
    Per D-03: 将 UE 类型映射为 C++ 类型名。
    Per D-04: 将 CPF 标志转换为 UPROPERTY 标记。
    Per D-05: 构建 header_meta（includes + generated_include）。
    从图节点提取方法声明填充 methods。

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

    # 5. 提取输入动作变量（从图节点）
    if result.graphs:
        properties.extend(_extract_input_action_properties(result.graphs))

    # 6. 提取方法声明
    methods: List[CppMethodIR] = []
    if result.graphs:
        blueprint_functions = getattr(blueprint, 'functions', None)
        methods = extract_cpp_functions(
            result.graphs,
            blueprint_functions=blueprint_functions,
            linker=result.linker,
        )

    # 6. 补齐缺失方法（第三条路径 — 从 decompiled_functions 直接生成 CppMethodIR）
    if hasattr(result, 'decompiled_functions') and result.decompiled_functions:
        _backfill_missing_methods(methods, result.decompiled_functions)

    # 6. 注入函数体（从 decompiled_functions）
    if methods and hasattr(result, 'decompiled_functions') and result.decompiled_functions:
        _inject_function_bodies(methods, result.decompiled_functions)

    # 6.1 设置 class_name（用于 .cpp 实现中 ClassName::Method 前缀）
    for method in methods:
        if not method.class_name:
            method.class_name = class_name

    # 7. 构建 header_meta（Per D-05）
    header_meta = CppHeaderMeta.build_from_parent(parent_class, class_name)

    # 7. 构建 CppClassIR
    ir = CppClassIR(
        name=class_name,
        parent_class=parent_class,
        header_meta=header_meta,
        properties=properties,
        methods=methods,
        constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [],
        },  # 填充
    )

    # 填充 constructor 字典
    components = result.components or []
    ir.constructor["component_creations"] = build_component_creations(ir)
    ir.constructor["component_assignments"] = build_component_assignments(components)
    ir.constructor["default_values"] = build_default_values(ir, blueprint.variables)

    # Blocker 2 fix: transform 数据也流入 default_values
    ir.constructor["default_values"].extend(build_transform_assignments(ir, components))

    # 生成完整构造函数文本
    ir.constructor["constructor_text"] = format_cpp_constructor(ir)

    return ir


# ============================================================================
# 函数图提取（主入口）
# ============================================================================

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
                # 检查 b_override_function（可能在 node_data 中）
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


# ============================================================================
# 调用语句提取
# ============================================================================

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
# 构造函数提取
# ============================================================================


def extract_cpp_constructor(ir: "CppClassIR") -> str:
    """从 CppClassIR 生成完整的 C++ 构造函数文本。

    便捷函数，调用 format_cpp_constructor 生成构造函数代码。

    Args:
        ir: CppClassIR 实例（constructor 字典已填充）

    Returns:
        完整的 C++ 构造函数文本
    """
    return format_cpp_constructor(ir)


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "extract_cpp_class_skeleton",
    "extract_cpp_functions",
    "extract_cpp_call_statements",
    "extract_cpp_constructor",
    "_sanitize_identifier",
    "_derive_call_target",
]
