"""N2C 处理器模块 — 批量注册入口。"""
from uasset_read.n2c.processors.call_function import CallFunctionProcessor
from uasset_read.n2c.processors.cast import CastProcessor
from uasset_read.n2c.processors.comment import CommentProcessor
from uasset_read.n2c.processors.delegate import DelegateProcessor
from uasset_read.n2c.processors.enhanced_input import EnhancedInputActionProcessor
from uasset_read.n2c.processors.event import EventProcessor
from uasset_read.n2c.processors.fallback import FallbackProcessor
from uasset_read.n2c.processors.flow_control import (
    DoOnceProcessor,
    EaseFunctionProcessor,
    FlowControlProcessor,
    ForEachEnumProcessor,
    MapForEachProcessor,
    MultiGateProcessor,
    SelectProcessor,
    SetForEachProcessor,
)
from uasset_read.n2c.processors.function_entry import FunctionEntryProcessor
from uasset_read.n2c.processors.struct_ops import (
    BreakStructProcessor,
    MakeArrayProcessor,
    MakeMapProcessor,
    MakeSetProcessor,
    MakeStructProcessor,
    StructOpsProcessor,
)
from uasset_read.n2c.processors.utilities import (
    AsyncActionProcessor,
    EnumComparisonProcessor,
    FormatTextProcessor,
    GetEnumeratorNameAsStringProcessor,
    GetEnumeratorNameProcessor,
    GetNumEnumEntriesProcessor,
    MathExpressionProcessor,
    TimelineProcessor,
)
from uasset_read.n2c.processors.variable import VariableProcessor
from uasset_read.n2c.processors.variable_ops import (
    ClearDelegateProcessor,
    CreateDelegateProcessor,
    DelegateSetProcessor,
    LocalVariableProcessor,
    RemoveDelegateProcessor,
    SetFieldsInStructProcessor,
    StructMemberGetProcessor,
    StructMemberSetProcessor,
)
from uasset_read.n2c.processors.widget import WidgetProcessor

__all__ = [
    # 原有处理器
    "CallFunctionProcessor",
    "CastProcessor",
    "CommentProcessor",
    "DelegateProcessor",
    "EnhancedInputActionProcessor",
    "EventProcessor",
    "FallbackProcessor",
    "FlowControlProcessor",
    "FunctionEntryProcessor",
    "VariableProcessor",
    "WidgetProcessor",
    # flow_control 扩展
    "DoOnceProcessor",
    "EaseFunctionProcessor",
    "ForEachEnumProcessor",
    "MapForEachProcessor",
    "MultiGateProcessor",
    "SelectProcessor",
    "SetForEachProcessor",
    # struct_ops
    "BreakStructProcessor",
    "MakeArrayProcessor",
    "MakeMapProcessor",
    "MakeSetProcessor",
    "MakeStructProcessor",
    "StructOpsProcessor",
    # variable_ops
    "ClearDelegateProcessor",
    "CreateDelegateProcessor",
    "DelegateSetProcessor",
    "LocalVariableProcessor",
    "RemoveDelegateProcessor",
    "SetFieldsInStructProcessor",
    "StructMemberGetProcessor",
    "StructMemberSetProcessor",
    # utilities
    "AsyncActionProcessor",
    "EnumComparisonProcessor",
    "FormatTextProcessor",
    "GetEnumeratorNameAsStringProcessor",
    "GetEnumeratorNameProcessor",
    "GetNumEnumEntriesProcessor",
    "MathExpressionProcessor",
    "TimelineProcessor",
    "register_all_processors",
]


def register_all_processors() -> None:
    """批量注册所有处理器到全局注册表（幂等：跳过已注册的类型）。"""
    from uasset_read.n2c.processor_registry import get_registry

    registry = get_registry()
    for proc_cls in [
        # 原有处理器
        CallFunctionProcessor,
        CommentProcessor,
        DelegateProcessor,
        EnhancedInputActionProcessor,
        EventProcessor,
        FunctionEntryProcessor,
        FlowControlProcessor,
        VariableProcessor,
        CastProcessor,
        WidgetProcessor,
        # flow_control 扩展
        MultiGateProcessor,
        DoOnceProcessor,
        SelectProcessor,
        EaseFunctionProcessor,
        ForEachEnumProcessor,
        MapForEachProcessor,
        SetForEachProcessor,
        # struct_ops
        StructOpsProcessor,
        MakeArrayProcessor,
        MakeMapProcessor,
        MakeSetProcessor,
        # variable_ops
        LocalVariableProcessor,
        CreateDelegateProcessor,
        ClearDelegateProcessor,
        RemoveDelegateProcessor,
        DelegateSetProcessor,
        StructMemberGetProcessor,
        StructMemberSetProcessor,
        SetFieldsInStructProcessor,
        # utilities
        AsyncActionProcessor,
        TimelineProcessor,
        FormatTextProcessor,
        MathExpressionProcessor,
        GetEnumeratorNameProcessor,
        GetEnumeratorNameAsStringProcessor,
        GetNumEnumEntriesProcessor,
        EnumComparisonProcessor,
    ]:
        try:
            registry.register(proc_cls())
        except ValueError:
            pass  # Already registered, skip (idempotent)
    if registry._fallback is None:
        registry.set_fallback(FallbackProcessor())
