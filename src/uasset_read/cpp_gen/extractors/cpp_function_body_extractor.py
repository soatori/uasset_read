"""C++ 函数体提取模块 — 从 execution_flows / data_flows 生成 CppStatement 树。

将蓝图函数体逻辑翻译为中间 IR 结构。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppAssignmentStmt,
    CppCallStmt,
    CppForEachStmt,
    CppForStmt,
    CppIfStmt,
    CppInlineExprStmt,
    CppMethodIR,
    CppRawStmt,
    CppStatement,
    CppWhileStmt,
)
from uasset_read.graph.macro_expander import STANDARD_MACRO_CPP_MAPPING

logger = logging.getLogger(__name__)


# ============================================================================
# Pure 函数内联映射表（D-58-04）
# ============================================================================

PURE_FUNCTION_INLINE_MAP: Dict[str, Callable] = {
    "Multiply_VectorFloat": lambda a, b: f"{a} * {b}",
    "Add_VectorVector": lambda a, b: f"{a} + {b}",
    "Subtract_VectorVector": lambda a, b: f"{a} - {b}",
    "Multiply_FloatFloat": lambda a, b: f"{a} * {b}",
    "DEFAULT": lambda name, args: f"{name}({', '.join(args)})",
}


def _build_call_expression(func_name: str, args: List[str]) -> str:
    """从函数名和参数构建 C++ 调用表达式。"""
    inline_fn = PURE_FUNCTION_INLINE_MAP.get(func_name, PURE_FUNCTION_INLINE_MAP["DEFAULT"])
    if inline_fn is PURE_FUNCTION_INLINE_MAP["DEFAULT"]:
        return inline_fn(func_name, args)
    return inline_fn(*args)


def _sanitize_identifier(name: str) -> str:
    """将 UE pin 名清理为 C++ 标识符。"""
    # 移除空格和斜杠： "Left / Right" → "LeftRight"
    cleaned = name.replace(" ", "").replace("/", "").replace("-", "_")
    if not cleaned:
        return "unnamed"
    return cleaned


def _resolve_target(node_info: Dict, method_ir: CppMethodIR) -> Tuple[str, str]:
    """从 CallFunction 节点推导调用目标和类型。

    Returns:
        (target, target_type) — target_type 为 "this" | "pointer" | "super"
    """
    params = node_info.get("parameters", {})
    fr = params.get("function_reference", {}) if isinstance(params, dict) else {}
    member_parent = fr.get("member_parent", "")
    b_self_context = fr.get("b_self_context", True)

    # Super 调用检测
    if member_parent and member_parent != method_ir.cpp_name and not b_self_context:
        return ("Super", "super")

    if not b_self_context:
        target_name = member_parent if member_parent else "this"
        return (target_name, "pointer")

    return ("this", "this")


# ============================================================================
# 核心函数：extract_function_body
# ============================================================================

def extract_function_body(
    method_ir: CppMethodIR,
    execution_flow: Dict,
    data_flows: List[Dict],
    node_lookup: Dict,
) -> List[CppStatement]:
    """从执行流和数据流生成函数体语句序列。

    Args:
        method_ir: 方法 IR（含签名信息）
        execution_flow: execution_flows 中的单个 flow（含 nodes 列表）
        data_flows: 数据流列表（用于参数推导）
        node_lookup: node_guid → node 查找表（用于获取完整 pin 信息）

    Returns:
        CppStatement 列表
    """
    nodes = execution_flow.get("nodes", [])
    statements: List[CppStatement] = []

    for node_info in nodes:
        node_type = node_info.get("node_type", "")

        # 跳过 FunctionEntry 本身
        if node_type == "K2Node_FunctionEntry":
            continue

        if node_type == "K2Node_CallFunction":
            stmt = _translate_call_function(node_info, method_ir, data_flows)
            if stmt is not None:
                statements.append(stmt)

        elif node_type in ("K2Node_IfThenElse", "K2Node_SwitchInteger",
                           "K2Node_SwitchString", "K2Node_SwitchEnum"):
            if_stmt = _translate_control_flow(node_info, method_ir, data_flows, node_lookup)
            if if_stmt is not None:
                statements.append(if_stmt)

        elif node_type == "K2Node_MacroInstance":
            stmt = _translate_macro_instance(node_info, method_ir, data_flows, node_lookup)
            if stmt is not None:
                statements.append(stmt)

        elif node_type == "K2Node_FunctionResult":
            # 函数返回点，在纯语句序列中不生成显式语句
            continue

        else:
            logger.debug(f"Unhandled node type in function body: {node_type}")

    return statements


def _translate_call_function(
    node_info: Dict,
    method_ir: CppMethodIR,
    data_flows: List[Dict],
) -> Optional[CppStatement]:
    """翻译单个 K2Node_CallFunction 节点为 CppStatement。"""
    func_name = node_info.get("function_name", "Unknown")
    is_pure = node_info.get("pure", False)

    # 推导参数
    args = _extract_call_args(node_info, method_ir, data_flows)

    # 推导调用目标
    target, target_type = _resolve_target(node_info, method_ir)

    if is_pure:
        # Pure 函数：走内联决策
        return _decide_pure_inline(node_info, func_name, args, data_flows)

    # 非 pure 函数调用 → CppCallStmt
    if target_type == "super":
        return CppCallStmt(
            target="Super",
            method_name=func_name,
            args=args,
            is_pure=False,
        )
    elif target_type == "pointer":
        return CppCallStmt(
            target=target,
            method_name=func_name,
            args=args,
            is_pure=False,
        )
    else:
        return CppCallStmt(
            target="this",
            method_name=func_name,
            args=args,
            is_pure=False,
        )


def _extract_call_args(
    node_info: Dict,
    method_ir: CppMethodIR,
    data_flows: List[Dict],
) -> List[str]:
    """从 CallFunction 节点的 parameters 和 data_flows 推导参数列表。

    优先通过 data_flows 解析参数来源（function_parameter → 函数签名参数名），
    避免使用 CallFunction 节点自身的 pin 名（如 "Val"），而是追溯到数据源头
    （如 FunctionEntry 的 "Pitch"）。
    """
    params = node_info.get("parameters", {})
    param_list = params.get("parameters", []) if isinstance(params, dict) else []
    node_guid = node_info.get("guid", "")

    # 构建数据流查找表：(target_node_guid, input_pin) → 解析后的参数名
    flow_lookup = _build_data_flow_lookup(data_flows)

    args: List[str] = []
    for param in param_list:
        if isinstance(param, dict):
            name = param.get("name", "")
            direction = param.get("direction", "input")
            # 跳过 exec/return 参数
            if direction in ("exec", "return"):
                continue
            if name:
                # 优先通过数据流解析
                resolved = _resolve_param_via_data_flow(
                    node_guid, name, flow_lookup
                )
                if resolved:
                    args.append(resolved)
                else:
                    # 回退：使用原始 pin 名
                    args.append(_sanitize_identifier(name))

    # Fallback: 从 data_sources 推导（当 param_list 为空时）
    if not args:
        data_sources = node_info.get("data_sources", [])
        for ds in data_sources:
            if isinstance(ds, dict):
                pin = ds.get("input_pin", "")
                source = ds.get("data_source", {})
                if isinstance(source, dict):
                    sources_list = source.get("data_sources", [])
                    for src in sources_list:
                        if isinstance(src, dict):
                            src_type = src.get("source_type", "")
                            if src_type == "function_parameter":
                                src_pin = src.get("pin", "")
                                args.append(_sanitize_identifier(src_pin))
                            elif src_type == "default_value":
                                args.append(src.get("value", "0"))
                            elif src_type == "pure_function":
                                args.append(src.get("function_name", "Unknown"))

    return args


def _build_data_flow_lookup(data_flows: List[Dict]) -> Dict:
    """构建数据流查找表：(target_node_name, input_pin) → 解析后的参数名。

    遍历所有 data_flows，提取每个目标节点的输入 pin 对应的数据源。
    如果数据源是 function_parameter（来自 FunctionEntry），则记录其 pin 名。
    支持通过 Knot 节点追溯数据源。
    """
    # 第一遍：构建直接连接和 Knot 节点的映射
    direct_lookup = {}  # (target_node, target_pin) → source info
    knot_outputs = {}   # knot_node → source info (from its OutputPin)

    for flow in data_flows:
        source = flow.get("source", {})
        target = flow.get("target", {})

        if not isinstance(source, dict) or not isinstance(target, dict):
            continue

        source_node = source.get("node", "")
        source_pin = source.get("pin", "")
        target_node = target.get("node", "")
        target_pin = target.get("pin", "")

        # 检查是否是 FunctionEntry 的直接输出
        if "FunctionEntry" in source_node:
            key = (target_node, target_pin)
            direct_lookup[key] = _sanitize_identifier(source_pin)

        # 记录 Knot 节点的输出（用于后续追溯）
        if "Knot" in source_node and source_pin == "OutputPin":
            # 这个 Knot 的输出来自哪里？需要回溯
            knot_outputs[target_node] = source_node  # 记录 Knot 的输入来源

    # 第二遍：追溯通过 Knot 的连接
    # 如果 target 是 Knot，我们需要找到 Knot 的 OutputPin 连接到哪里
    knot_to_source = {}  # knot_node → ultimate source param name

    for flow in data_flows:
        source = flow.get("source", {})
        target = flow.get("target", {})

        if not isinstance(source, dict) or not isinstance(target, dict):
            continue

        source_node = source.get("node", "")
        source_pin = source.get("pin", "")
        target_node = target.get("node", "")
        target_pin = target.get("pin", "")

        # 如果目标是 Knot 的 InputPin，记录这个 Knot 的来源
        if "Knot" in target_node and target_pin == "InputPin":
            if "FunctionEntry" in source_node:
                knot_to_source[target_node] = _sanitize_identifier(source_pin)

    # 第三遍：构建最终查找表，包括通过 Knot 的连接
    lookup = dict(direct_lookup)

    for flow in data_flows:
        source = flow.get("source", {})
        target = flow.get("target", {})

        if not isinstance(source, dict) or not isinstance(target, dict):
            continue

        source_node = source.get("node", "")
        source_pin = source.get("pin", "")
        target_node = target.get("node", "")
        target_pin = target.get("pin", "")

        # 如果来源是 Knot，追溯其 ultimate source
        if "Knot" in source_node and source_pin == "OutputPin":
            ultimate_source = knot_to_source.get(source_node, "")
            if ultimate_source:
                key = (target_node, target_pin)
                lookup[key] = ultimate_source

    return lookup


def _resolve_param_via_data_flow(
    node_guid: str,
    pin_name: str,
    flow_lookup: Dict,
) -> Optional[str]:
    """尝试通过数据流查找表解析参数名。

    Args:
        node_guid: 当前 CallFunction 节点的 GUID
        pin_name: 输入 pin 名（如 "Val"）
        flow_lookup: 数据流查找表

    Returns:
        解析后的参数名（如 "Pitch"），如果未找到则返回 None
    """
    key = (node_guid, pin_name)
    return flow_lookup.get(key)


# ============================================================================
# Pure 函数内联决策（D-58-04）
# ============================================================================

def _decide_pure_inline(
    node_info: Dict,
    func_name: str,
    args: List[str],
    data_flows: List[Dict],
) -> CppStatement:
    """决定 pure 函数是内联还是创建中间变量。

    规则：
    - 单一使用者 → CppInlineExprStmt
    - 多使用者 → CppAssignmentStmt（临时变量）
    """
    data_providers = node_info.get("data_providers", [])
    user_count = len(data_providers) if data_providers else 1

    expression = _build_call_expression(func_name, args)

    if user_count <= 1:
        return CppInlineExprStmt(expression=expression)
    else:
        # 多使用者：创建临时变量
        temp_var = f"_temp_{func_name.lower()}"
        return CppAssignmentStmt(
            lhs=temp_var,
            rhs=expression,
            cpp_type="auto",
        )


# ============================================================================
# 控制流节点翻译（D-58-01）
# ============================================================================

def _translate_control_flow(
    node_info: Dict,
    method_ir: CppMethodIR,
    data_flows: List[Dict],
    node_lookup: Dict,
) -> Optional[CppStatement]:
    """翻译控制流节点（IfThenElse / Switch*）为 CppIfStmt。"""
    node_type = node_info.get("node_type", "")
    branch_type = node_info.get("branch_type", "unknown")

    # 推导条件表达式
    condition = _derive_condition(node_info, data_flows)

    if node_type == "K2Node_MacroInstance":
        return _translate_macro_instance(node_info, method_ir, data_flows, node_lookup)

    # K2Node_Switch* 暂时翻译为 if-else if-else 链
    # then_body 和 else_body 需要从执行流的分支中推导
    # 当前实现：使用占位条件，分支体为空
    return CppIfStmt(
        condition=condition,
        then_body=[],
        else_body=[],
    )


def _derive_condition(node_info: Dict, data_flows: List[Dict]) -> str:
    """从控制流节点的 data_sources 推导条件表达式。"""
    data_sources = node_info.get("data_sources", [])
    if data_sources:
        for ds in data_sources:
            if isinstance(ds, dict):
                input_pin = ds.get("input_pin", "")
                source = ds.get("data_source", {})
                if isinstance(source, dict):
                    for src in source.get("data_sources", []):
                        if isinstance(src, dict):
                            if src.get("source_type") == "default_value":
                                val = src.get("value", "")
                                if val.lower() in ("true", "false"):
                                    return val.lower()
                                return val
                            elif src.get("source_type") == "function_parameter":
                                return _sanitize_identifier(src.get("pin", "condition"))

    # Fallback: 从节点类型推导默认条件
    branch_type = node_info.get("branch_type", "unknown")
    if branch_type == "if":
        return "condition"
    elif branch_type.startswith("switch"):
        return f"switch_{branch_type.split('_')[-1] if '_' in branch_type else 'value'}"

    return "condition"


# ============================================================================
# 宏实例翻译（蓝图宏 → C++ 控制流）
# ============================================================================

def _translate_macro_instance(
    node_info: Dict,
    method_ir: CppMethodIR,
    data_flows: List[Dict],
    node_lookup: Dict,
) -> Optional[CppStatement]:
    """翻译 MacroInstance 节点为 CppStatement。

    策略：
    1. 标准宏 → 根据 STANDARD_MACRO_CPP_MAPPING 生成对应 C++ 控制流 IR
    2. 非标准宏 → 使用 macro_internal_flows 递归翻译内部节点
    3. 未知宏 → 输出注释
    """
    expansion = node_info.get("macro_expansion", {})
    macro_name = expansion.get("macro_name", "")
    is_standard = expansion.get("is_standard", False)

    if is_standard and macro_name in STANDARD_MACRO_CPP_MAPPING:
        return _translate_standard_macro(macro_name, expansion, node_info, data_flows)

    internal_flows = node_info.get("macro_internal_flows", [])
    if internal_flows:
        return _translate_user_macro(internal_flows, method_ir, data_flows, node_lookup)

    return CppRawStmt(raw_text=f"/* macro: {macro_name or 'Unknown'} */")


def _translate_standard_macro(
    macro_name: str,
    expansion: Dict,
    node_info: Dict,
    data_flows: List[Dict],
) -> CppStatement:
    """翻译标准宏为 C++ 控制流 IR。"""
    mapping = STANDARD_MACRO_CPP_MAPPING.get(macro_name, {})
    cpp_stmt_type = mapping.get("cpp_statement", "unknown")
    condition = _derive_condition_from_macro(expansion, data_flows)

    if cpp_stmt_type == "for":
        pin_mapping = expansion.get("pin_mapping", {})
        counter = "LoopCounter" if "Loop Counter" in pin_mapping else "_counter"
        first = _get_pin_default(pin_mapping, "FirstIndex", "0")
        last = _get_pin_default(pin_mapping, "LastIndex", "N")
        inc = _get_pin_default(pin_mapping, "Increment", "1")
        return CppForStmt(
            init=f"int {counter} = {first}",
            condition=f"{counter} <= {last}",
            increment=f"{counter} += {inc}",
        )

    elif cpp_stmt_type == "while":
        return CppWhileStmt(condition=condition)

    elif cpp_stmt_type == "for_each":
        pin_mapping = expansion.get("pin_mapping", {})
        element = _get_pin_default(pin_mapping, "Array Element", "Element")
        container = _get_pin_default(pin_mapping, "Array", "Array")
        return CppForEachStmt(
            element=element,
            container=container,
        )

    elif cpp_stmt_type == "if":
        return CppIfStmt(
            condition=condition,
            then_body=[],
            else_body=[],
        )

    else:
        template = mapping.get("cpp_template", f"/* {macro_name} */")
        return CppRawStmt(raw_text=template)


def _translate_user_macro(
    internal_flows: List[Dict],
    method_ir: CppMethodIR,
    data_flows: List[Dict],
    node_lookup: Dict,
) -> CppStatement:
    """翻译用户自定义宏的内部执行流为 CppStatement。"""
    stmts: List[CppStatement] = []
    for flow in internal_flows:
        nodes = flow.get("nodes", [])
        for node_info in nodes:
            node_type = node_info.get("node_type", "")
            if node_type == "K2Node_CallFunction":
                stmt = _translate_call_function(node_info, method_ir, data_flows)
                if stmt is not None:
                    stmts.append(stmt)
    if len(stmts) == 1:
        return stmts[0]
    return CppRawStmt(raw_text=f"/* user macro: {len(stmts)} statements */")


def _derive_condition_from_macro(expansion: Dict, data_flows: List[Dict]) -> str:
    """从宏展开的 pin_mapping 推导条件表达式。"""
    pin_mapping = expansion.get("pin_mapping", {})
    for key in ("Condition", "Input"):
        if key in pin_mapping:
            pin_info = pin_mapping[key]
            default_val = pin_info.get("default_value", "")
            if default_val:
                return default_val
    return "condition"


def _get_pin_default(pin_mapping: Dict, pin_name: str, default: str) -> str:
    """从 pin_mapping 获取引脚的默认值。"""
    if pin_name in pin_mapping:
        val = pin_mapping[pin_name].get("default_value", "")
        if val:
            return val
    return default
