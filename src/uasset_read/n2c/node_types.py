"""临时语义类型枚举 — Phase 68 N2CNodeTypeRegistry 就绪后替换。"""
from enum import Enum


class N2CNodeType(Enum):
    """临时语义类型枚举。

    覆盖 Phase 69 处理器所需的 K2Node 语义类型。
    Phase 68 完成后将从 N2CNodeTypeRegistry 获取权威枚举。
    """
    CallFunction = "CallFunction"
    Event = "Event"
    CustomEvent = "CustomEvent"
    FunctionEntry = "FunctionEntry"
    FunctionResult = "FunctionResult"
    VariableGet = "VariableGet"
    VariableSet = "VariableSet"
    Branch = "Branch"           # K2Node_IfThenElse
    Sequence = "Sequence"       # K2Node_ExecutionSequence
    SwitchInt = "SwitchInt"     # K2Node_SwitchInteger
    SwitchString = "SwitchString"
    SwitchEnum = "SwitchEnum"
    DynamicCast = "DynamicCast"
    ClassDynamicCast = "ClassDynamicCast"
    MakeStruct = "MakeStruct"
    BreakStruct = "BreakStruct"
    MakeArray = "MakeArray"
    MakeMap = "MakeMap"
    MakeSet = "MakeSet"
    AddDelegate = "AddDelegate"
    CreateDelegate = "CreateDelegate"
    ClearDelegate = "ClearDelegate"
    AsyncAction = "AsyncAction"
    SpawnActor = "SpawnActor"
    Timeline = "Timeline"
    FormatText = "FormatText"
    LocalVariable = "LocalVariable"
    MathExpression = "MathExpression"
    EnumLiteral = "EnumLiteral"
    BitmaskLiteral = "BitmaskLiteral"
    Unknown = "Unknown"
