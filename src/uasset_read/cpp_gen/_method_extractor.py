"""C++ 类骨架提取 — 方法提取和函数体注入。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Tuple

from uasset_read.cpp_gen.formatters import CppMethodIR, CppCallParameter
from uasset_read.cpp_gen.cpp_type_mapper import ue_path_to_cpp_type
from uasset_read.cpp_gen.sanitizer import sanitize_identifier as _sanitize_identifier
from uasset_read.cpp_gen._property_extractor import _extract_cpp_type_from_pin

if TYPE_CHECKING:
    from uasset_read.link.result import LinkerParseResult

logger = logging.getLogger(__name__)


# ============================================================================
# 函数标志位常量（UE5 UFunctionFlags）- 参考 EFunctionFlags.cs
# ============================================================================

# 访问修饰符（这些标志不在 extra_flags 中，需要从其他来源推断）
FUNC_PUBLIC = 0x00000001  # 占位符，实际访问修饰符需要从其他信息推断
FUNC_PROTECTED = 0x00000002  # 占位符
FUNC_PRIVATE = 0x00000004  # 占位符

# 函数类型（参考 EFunctionFlags.cs）
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


# ============================================================================
# 辅助函数
# ============================================================================

def _extractFunctionFlags(flags: int) -> Dict[str, bool]:
    """从 extra_flags 提取函数标志位。

    参考 EFunctionFlags.cs 的定义。

    Args:
        flags: extra_flags 值

    Returns:
        函数标志字典
    """
    return {
        # 访问修饰符（需要从其他信息推断）
        "is_public": False,  # 默认
        "is_protected": True,  # 默认
        "is_private": False,
        # 函数类型
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
    node_class_name: str,
    is_override: bool,
    extra_flags: int = 0
) -> List[str]:
    """推断 UFUNCTION 修饰符（D-57-03）。

    改进：从 extra_flags 提取标志位。
    """
    if is_override:
        return []

    # 从 extra_flags 提取标志
    flags = _extractFunctionFlags(extra_flags)

    # 如果 extra_flags 已经设置了 BlueprintPure/BlueprintCallable，直接使用
    if flags["is_blueprint_pure"]:
        return ["BlueprintPure"]
    if flags["is_blueprint_callable"]:
        return ["BlueprintCallable"]

    # 回退到从引脚推断
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


def _build_param_name_map(method: CppMethodIR) -> Dict[str, str]:
    """构建 {原始参数名模式 -> sanitized名} 映射。

    Sanitizer 将 '/' 等非法字符替换为 '__'。例如：
    - 'Left / Right' → 'Left__Right'
    - 'Forward / Backward' → 'Forward__Backward'

    反向推导：如果 sanitized 名包含 '__'，构造对应的 ' / ' 模式。
    """
    name_map = {}
    for param in method.parameters:
        if '__' in param.name:
            # 反向推导原始名：'__' → ' / '
            original = param.name.replace('__', ' / ')
            name_map[original] = param.name
    return name_map


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


# ============================================================================
# 方法构建
# ============================================================================

def _build_cpp_method_from_entry(
    fe_node: "K2NodeFunctionEntry",
    blueprint_functions: Dict
) -> CppMethodIR:
    """从 K2Node_FunctionEntry 构建 CppMethodIR。

    改进：从 extra_flags 提取函数标志。
    """
    # 从 node_data 获取 function_reference（可能在 node_data 字典中）
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

    # 提取函数标志
    flags = _extractFunctionFlags(extra_flags)

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

    specifiers = _infer_ufunction_specifiers(
        fe_node.pins,
        "K2Node_FunctionEntry",
        is_override=False,
        extra_flags=extra_flags
    )

    # 确定访问修饰符
    access_modifier = "protected"  # 默认
    if flags["is_public"]:
        access_modifier = "public"
    elif flags["is_private"]:
        access_modifier = "private"

    return CppMethodIR(
        cpp_name=_sanitize_identifier(func_name),
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
    """从 K2Node_Event 构建 CppMethodIR（is_override=True）。"""
    # 从 node_data 获取 event_reference
    event_ref = None
    nd = event_node.node_data

    if nd is not None:
        if isinstance(nd, dict):
            # 字典格式：直接从字典获取
            event_ref = nd.get('event_reference')
        else:
            # 对象格式：使用 getattr
            event_ref = getattr(nd, 'event_reference', None)

    # 尝试从节点属性获取
    if event_ref is None:
        event_ref = getattr(event_node, 'event_reference', None)

    if event_ref is None:
        return None

    event_name = event_ref.member_name if hasattr(event_ref, 'member_name') else None
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


# ============================================================================
# 函数体注入与补齐
# ============================================================================

def _inject_function_bodies(
    methods: List[CppMethodIR],
    decompiled_functions: List[Any],
) -> None:
    """将 KismetDecompiledResult 的 cpp_code 注入到 CppMethodIR.body_text。

    匹配逻辑：
    1. 精确匹配：function_name == cpp_name
    2. 清理后匹配：function_name 清理后 == cpp_name
    3. 大小写不敏感匹配

    注入前执行符号映射替换，确保函数体内变量名与方法声明一致。

    Args:
        methods: CppMethodIR 列表（已填充方法声明）
        decompiled_functions: KismetDecompiledResult 列表（含 cpp_code）
    """
    method_index: Dict[str, CppMethodIR] = {m.cpp_name: m for m in methods}

    for decompiled in decompiled_functions:
        func_name = decompiled.function_name

        # 精确匹配
        method = method_index.get(func_name)

        # 清理后匹配
        if method is None:
            sanitized = _sanitize_identifier(func_name)
            method = method_index.get(sanitized)

        # 大小写不敏感匹配
        if method is None:
            for cpp_name, m in method_index.items():
                if func_name.lower() == cpp_name.lower():
                    method = m
                    break

        if method and decompiled.cpp_code:
            body = decompiled.cpp_code
            # 执行符号映射替换：原始参数名 → sanitized 名
            for original, sanitized in _build_param_name_map(method).items():
                body = body.replace(original, sanitized)
            method.body_text = body


def _backfill_missing_methods(
    methods: List[CppMethodIR],
    decompiled_functions: List[Any],
) -> None:
    """从 decompiled_functions 补齐 extract_cpp_functions 遗漏的 CppMethodIR。

    原因：extract_cpp_functions 只处理 K2Node_FunctionEntry 和
    K2Node_Event(b_override=True)，但部分反编译函数无对应图节点
    （如 ExecuteUbergraph、UserConstructionScript、InputAction 事件）。
    """
    existing_names = {m.cpp_name for m in methods}
    for decompiled in decompiled_functions:
        sanitized = _sanitize_identifier(decompiled.function_name)
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
