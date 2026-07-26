"""C++ function body extraction module — generates CppStatement trees from execution_flows / data_flows.

Translates blueprint function body logic into intermediate IR structures.
"""

import logging
from typing import Callable, Dict, List, Optional, Tuple

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
from uasset_read.cpp_gen.sanitizer import sanitize_identifier
from uasset_read.graph.macro_expander import STANDARD_MACRO_CPP_MAPPING

logger = logging.getLogger(__name__)


# ============================================================================
# Pure function inline mapping table (D-58-04)
# ============================================================================

PURE_FUNCTION_INLINE_MAP: Dict[str, Callable] = {
    "Multiply_VectorFloat": lambda a, b: f"{a} * {b}",
    "Add_VectorVector": lambda a, b: f"{a} + {b}",
    "Subtract_VectorVector": lambda a, b: f"{a} - {b}",
    "Multiply_FloatFloat": lambda a, b: f"{a} * {b}",
    "DEFAULT": lambda name, args: f"{name}({', '.join(args)})",
}


def _build_call_expression(func_name: str, args: List[str]) -> str:
    """Build C++ call expression from function name and arguments."""
    inline_fn = PURE_FUNCTION_INLINE_MAP.get(func_name, PURE_FUNCTION_INLINE_MAP["DEFAULT"])
    if inline_fn is PURE_FUNCTION_INLINE_MAP["DEFAULT"]:
        return inline_fn(func_name, args)
    return inline_fn(*args)




def _resolve_target(node_info: Dict, method_ir: CppMethodIR) -> Tuple[str, str]:
    """Derive call target and type from a CallFunction node.

    Returns:
        (target, target_type) — target_type is "this" | "pointer" | "super"
    """
    params = node_info.get("parameters", {})
    fr = params.get("function_reference", {}) if isinstance(params, dict) else {}
    member_parent = fr.get("member_parent", "")
    b_self_context = fr.get("b_self_context", True)

    # Super call detection
    if member_parent and member_parent != method_ir.cpp_name and not b_self_context:
        return ("Super", "super")

    if not b_self_context:
        target_name = member_parent if member_parent else "this"
        return (target_name, "pointer")

    return ("this", "this")


# ============================================================================
# Core function: extract_function_body
# ============================================================================

def extract_function_body(
    method_ir: CppMethodIR,
    execution_flow: Dict,
    data_flows: List[Dict],
    node_lookup: Dict,
) -> List[CppStatement]:
    """Generate function body statement sequence from execution flow and data flows.

    Args:
        method_ir: method IR (contains signature information)
        execution_flow: single flow from execution_flows (contains nodes list)
        data_flows: data flow list (used for argument derivation)
        node_lookup: node_guid → node lookup table (used to retrieve full pin information)

    Returns:
        CppStatement list
    """
    nodes = execution_flow.get("nodes", [])
    statements: List[CppStatement] = []

    for node_info in nodes:
        node_type = node_info.get("node_type", "")

        # Skip FunctionEntry itself
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
            # Function return point, no explicit statement generated in pure statement sequence
            continue

        else:
            logger.debug(f"Unhandled node type in function body: {node_type}")

    return statements


def _translate_call_function(
    node_info: Dict,
    method_ir: CppMethodIR,
    data_flows: List[Dict],
) -> Optional[CppStatement]:
    """Translate a single K2Node_CallFunction node into CppStatement."""
    func_name = node_info.get("function_name", "Unknown")
    is_pure = node_info.get("pure", False)

    # Derive arguments
    args = _extract_call_args(node_info, method_ir, data_flows)

    # Derive call target
    target, target_type = _resolve_target(node_info, method_ir)

    if is_pure:
        # Pure function: go through inlining decision
        return _decide_pure_inline(node_info, func_name, args, data_flows)

    # Non-pure function call -> CppCallStmt
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
    """Derive parameter list from CallFunction node's parameters and data_flows."""
    params = node_info.get("parameters", {})
    param_list = params.get("parameters", []) if isinstance(params, dict) else []

    args: List[str] = []
    for param in param_list:
        if isinstance(param, dict):
            name = param.get("name", "")
            direction = param.get("direction", "input")
            # Skip exec/return parameters
            if direction in ("exec", "return"):
                continue
            if name:
                args.append(sanitize_identifier(name))

    # Fallback: derive from data_sources
    if not args:
        data_sources = node_info.get("data_sources", [])
        for ds in data_sources:
            if isinstance(ds, dict):
                _pin = ds.get("input_pin", "")  # noqa: F841 - extracted for clarity
                source = ds.get("data_source", {})
                if isinstance(source, dict):
                    sources_list = source.get("data_sources", [])
                    for src in sources_list:
                        if isinstance(src, dict):
                            src_type = src.get("source_type", "")
                            if src_type == "function_parameter":
                                src_pin = src.get("pin", "")
                                args.append(sanitize_identifier(src_pin))
                            elif src_type == "default_value":
                                args.append(src.get("value", "0"))
                            elif src_type == "pure_function":
                                args.append(src.get("function_name", "Unknown"))

    return args


# ============================================================================
# Pure function inlining decision (D-58-04)
# ============================================================================

def _decide_pure_inline(
    node_info: Dict,
    func_name: str,
    args: List[str],
    data_flows: List[Dict],
) -> CppStatement:
    """Decide whether pure function is inlined or creates intermediate variable.

    Rules:
    - Single user -> CppInlineExprStmt
    - Multiple users -> CppAssignmentStmt (temporary variable)
    """
    data_providers = node_info.get("data_providers", [])
    user_count = len(data_providers) if data_providers else 1

    expression = _build_call_expression(func_name, args)

    if user_count <= 1:
        return CppInlineExprStmt(expression=expression)
    else:
        # Multiple users: create temporary variable
        temp_var = f"_temp_{func_name.lower()}"
        return CppAssignmentStmt(
            lhs=temp_var,
            rhs=expression,
            cpp_type="auto",
        )


# ============================================================================
# Control flow node translation (D-58-01)
# ============================================================================

def _translate_control_flow(
    node_info: Dict,
    method_ir: CppMethodIR,
    data_flows: List[Dict],
    node_lookup: Dict,
) -> Optional[CppStatement]:
    """Translate control flow nodes (IfThenElse / Switch*) to CppIfStmt."""
    node_type = node_info.get("node_type", "")
    _branch_type = node_info.get("branch_type", "unknown")  # noqa: F841 - extracted for clarity

    # Derive condition expression
    condition = _derive_condition(node_info, data_flows)

    if node_type == "K2Node_MacroInstance":
        return _translate_macro_instance(node_info, method_ir, data_flows, node_lookup)

    # K2Node_Switch* temporarily translated to if-else if-else chain
    # then_body and else_body need to be derived from execution flow branches
    # Current implementation: use placeholder condition, branch bodies are empty
    return CppIfStmt(
        condition=condition,
        then_body=[],
        else_body=[],
    )


def _derive_condition(node_info: Dict, data_flows: List[Dict]) -> str:
    """Derive condition expression from control flow node's data_sources."""
    data_sources = node_info.get("data_sources", [])
    if data_sources:
        for ds in data_sources:
            if isinstance(ds, dict):
                _input_pin = ds.get("input_pin", "")  # noqa: F841 - extracted for clarity
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
                                return sanitize_identifier(src.get("pin", "condition"))

    # Fallback: derive default condition from node type
    branch_type = node_info.get("branch_type", "unknown")
    if branch_type == "if":
        return "condition"
    elif branch_type.startswith("switch"):
        return f"switch_{branch_type.split('_')[-1] if '_' in branch_type else 'value'}"

    return "condition"


# ============================================================================
# Macro instance translation (blueprint macro -> C++ control flow)
# ============================================================================

def _translate_macro_instance(
    node_info: Dict,
    method_ir: CppMethodIR,
    data_flows: List[Dict],
    node_lookup: Dict,
) -> Optional[CppStatement]:
    """Translate MacroInstance node to CppStatement.

    Strategy:
    1. Standard macro -> generate corresponding C++ control flow IR based on STANDARD_MACRO_CPP_MAPPING
    2. Non-standard macro -> use macro_internal_flows to recursively translate internal nodes
    3. Unknown macro -> output comment
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
    """Translate standard macro to C++ control flow IR."""
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
    """Translate user-defined macro internal execution flow to CppStatement."""
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
    """Derive condition expression from macro expansion's pin_mapping."""
    pin_mapping = expansion.get("pin_mapping", {})
    for key in ("Condition", "Input"):
        if key in pin_mapping:
            pin_info = pin_mapping[key]
            default_val = pin_info.get("default_value", "")
            if default_val:
                return default_val
    return "condition"


def _get_pin_default(pin_mapping: Dict, pin_name: str, default: str) -> str:
    """Get pin default value from pin_mapping."""
    if pin_name in pin_mapping:
        val = pin_mapping[pin_name].get("default_value", "")
        if val:
            return val
    return default
