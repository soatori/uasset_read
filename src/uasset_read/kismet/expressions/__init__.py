"""Kismet expression classes and token-to-class mapping."""
from __future__ import annotations

from uasset_read.kismet.tokens import EExprToken
from uasset_read.kismet.expressions.base import KismetExpression

# Variables
from uasset_read.kismet.expressions.variables import (
    EX_VariableBase, EX_LocalVariable, EX_InstanceVariable,
    EX_DefaultVariable, EX_LocalOutVariable, EX_ClassSparseDataVariable,
)

# Literals
from uasset_read.kismet.expressions.literals import (
    EX_IntConst, EX_FloatConst, EX_ByteConst, EX_IntConstByte,
    EX_Int64Const, EX_UInt64Const, EX_DoubleConst,
    EX_IntZero, EX_IntOne, EX_True, EX_False,
)

# String constants
from uasset_read.kismet.expressions.string_consts import (
    EX_StringConst, EX_UnicodeStringConst, EX_TextConst, EX_SoftObjectConst,
)

# Vector constants
from uasset_read.kismet.expressions.vector_consts import (
    EX_VectorConst, EX_RotationConst, EX_TransformConst, EX_Vector3fConst,
)

# Control flow
from uasset_read.kismet.expressions.control_flow import (
    EX_Jump, EX_JumpIfNot, EX_Skip, EX_ComputedJump,
    EX_PushExecutionFlow, EX_PopExecutionFlow, EX_PopExecutionFlowIfNot,
    EX_EndOfScript, EX_SkipOffsetConst,
)

# Assignments
from uasset_read.kismet.expressions.assignments import (
    EX_Let, EX_LetBase, EX_LetBool, EX_LetDelegate,
    EX_LetMulticastDelegate, EX_LetObj, EX_LetWeakObjPtr,
    EX_LetValueOnPersistentFrame,
)

# Functions
from uasset_read.kismet.expressions.functions import (
    EX_EndParmValue, EX_EndFunctionParms, EX_FinalFunction,
    EX_CallMath, EX_LocalFinalFunction, EX_VirtualFunction,
    EX_LocalVirtualFunction, EX_CallMulticastDelegate,
)

# Casts
from uasset_read.kismet.expressions.casts import (
    EX_CastBase, EX_Cast, EX_MetaCast, EX_DynamicCast,
    EX_ObjToInterfaceCast, EX_CrossInterfaceCast, EX_InterfaceToObjCast,
)

# Context
from uasset_read.kismet.expressions.context import (
    EX_Context, EX_Context_FailSilent, EX_ClassContext,
    EX_InterfaceContext, EX_StructMemberContext,
)

# Containers
from uasset_read.kismet.expressions.containers import (
    EX_SetArray, EX_EndArray, EX_SetMap, EX_EndMap,
    EX_SetSet, EX_EndSet, EX_ArrayConst, EX_EndArrayConst,
    EX_MapConst, EX_EndMapConst, EX_SetConst, EX_EndSetConst,
    EX_ArrayGetByRef,
)

# Structs
from uasset_read.kismet.expressions.structs import (
    EX_StructConst, EX_EndStructConst, EX_BitFieldConst, EX_PropertyConst,
)

# Delegates
from uasset_read.kismet.expressions.delegates import (
    EX_AddMulticastDelegate, EX_ClearMulticastDelegate, EX_BindDelegate,
    EX_RemoveMulticastDelegate, EX_InstanceDelegate,
)

# Special
from uasset_read.kismet.expressions.special import (
    FKismetSwitchCase,
    EX_Return, EX_Assert, EX_Nothing, EX_NothingInt32,
    EX_Self, EX_NoObject, EX_NoInterface, EX_SwitchValue,
    EX_InstrumentationEvent, EX_DeprecatedOp4A, EX_Breakpoint,
    EX_Tracepoint, EX_WireTracepoint, EX_FieldPathConst,
    EX_ObjectConst, EX_NameConst,
    EX_Unknown6E, EX_Unknown6F, EX_MaxSentinel,
)

# RTFM
from uasset_read.kismet.expressions.rtfm import (
    EX_AutoRtfmTransact, EX_AutoRtfmStopTransact, EX_AutoRtfmAbortIfNot,
)

# Token -> Class mapping for FKismetArchive.read_expression()
EXPR_CLASS_MAP: dict[EExprToken, type[KismetExpression]] = {
    # Variables
    EExprToken.EX_LocalVariable: EX_LocalVariable,
    EExprToken.EX_InstanceVariable: EX_InstanceVariable,
    EExprToken.EX_DefaultVariable: EX_DefaultVariable,
    EExprToken.EX_LocalOutVariable: EX_LocalOutVariable,
    EExprToken.EX_ClassSparseDataVariable: EX_ClassSparseDataVariable,
    # Control flow
    EExprToken.EX_Return: EX_Return,
    EExprToken.EX_Jump: EX_Jump,
    EExprToken.EX_JumpIfNot: EX_JumpIfNot,
    EExprToken.EX_Assert: EX_Assert,
    EExprToken.EX_Nothing: EX_Nothing,
    EExprToken.EX_NothingInt32: EX_NothingInt32,
    EExprToken.EX_Self: EX_Self,
    EExprToken.EX_NoObject: EX_NoObject,
    EExprToken.EX_NoInterface: EX_NoInterface,
    EExprToken.EX_EndOfScript: EX_EndOfScript,
    EExprToken.EX_DeprecatedOp4A: EX_DeprecatedOp4A,
    EExprToken.EX_Breakpoint: EX_Breakpoint,
    EExprToken.EX_Tracepoint: EX_Tracepoint,
    EExprToken.EX_WireTracepoint: EX_WireTracepoint,
    # Literals
    EExprToken.EX_IntConst: EX_IntConst,
    EExprToken.EX_FloatConst: EX_FloatConst,
    EExprToken.EX_ByteConst: EX_ByteConst,
    EExprToken.EX_IntConstByte: EX_IntConstByte,
    EExprToken.EX_Int64Const: EX_Int64Const,
    EExprToken.EX_UInt64Const: EX_UInt64Const,
    EExprToken.EX_DoubleConst: EX_DoubleConst,
    EExprToken.EX_IntZero: EX_IntZero,
    EExprToken.EX_IntOne: EX_IntOne,
    EExprToken.EX_True: EX_True,
    EExprToken.EX_False: EX_False,
    # String constants
    EExprToken.EX_StringConst: EX_StringConst,
    EExprToken.EX_UnicodeStringConst: EX_UnicodeStringConst,
    EExprToken.EX_TextConst: EX_TextConst,
    EExprToken.EX_SoftObjectConst: EX_SoftObjectConst,
    # Vector constants
    EExprToken.EX_VectorConst: EX_VectorConst,
    EExprToken.EX_RotationConst: EX_RotationConst,
    EExprToken.EX_TransformConst: EX_TransformConst,
    EExprToken.EX_Vector3fConst: EX_Vector3fConst,
    # Object/Name
    EExprToken.EX_ObjectConst: EX_ObjectConst,
    EExprToken.EX_NameConst: EX_NameConst,
    # Assignments
    EExprToken.EX_Let: EX_Let,
    EExprToken.EX_LetBool: EX_LetBool,
    EExprToken.EX_LetDelegate: EX_LetDelegate,
    EExprToken.EX_LetMulticastDelegate: EX_LetMulticastDelegate,
    EExprToken.EX_LetObj: EX_LetObj,
    EExprToken.EX_LetWeakObjPtr: EX_LetWeakObjPtr,
    EExprToken.EX_LetValueOnPersistentFrame: EX_LetValueOnPersistentFrame,
    # Functions
    EExprToken.EX_VirtualFunction: EX_VirtualFunction,
    EExprToken.EX_FinalFunction: EX_FinalFunction,
    EExprToken.EX_LocalVirtualFunction: EX_LocalVirtualFunction,
    EExprToken.EX_LocalFinalFunction: EX_LocalFinalFunction,
    EExprToken.EX_CallMath: EX_CallMath,
    EExprToken.EX_CallMulticastDelegate: EX_CallMulticastDelegate,
    EExprToken.EX_InstanceDelegate: EX_InstanceDelegate,
    EExprToken.EX_EndParmValue: EX_EndParmValue,
    EExprToken.EX_EndFunctionParms: EX_EndFunctionParms,
    # Casts
    EExprToken.EX_Cast: EX_Cast,
    EExprToken.EX_MetaCast: EX_MetaCast,
    EExprToken.EX_DynamicCast: EX_DynamicCast,
    EExprToken.EX_ObjToInterfaceCast: EX_ObjToInterfaceCast,
    EExprToken.EX_CrossInterfaceCast: EX_CrossInterfaceCast,
    EExprToken.EX_InterfaceToObjCast: EX_InterfaceToObjCast,
    # Context
    EExprToken.EX_Context: EX_Context,
    EExprToken.EX_Context_FailSilent: EX_Context_FailSilent,
    EExprToken.EX_ClassContext: EX_ClassContext,
    EExprToken.EX_InterfaceContext: EX_InterfaceContext,
    EExprToken.EX_StructMemberContext: EX_StructMemberContext,
    # Containers
    EExprToken.EX_SetArray: EX_SetArray,
    EExprToken.EX_EndArray: EX_EndArray,
    EExprToken.EX_SetMap: EX_SetMap,
    EExprToken.EX_EndMap: EX_EndMap,
    EExprToken.EX_SetSet: EX_SetSet,
    EExprToken.EX_EndSet: EX_EndSet,
    EExprToken.EX_ArrayConst: EX_ArrayConst,
    EExprToken.EX_EndArrayConst: EX_EndArrayConst,
    EExprToken.EX_MapConst: EX_MapConst,
    EExprToken.EX_EndMapConst: EX_EndMapConst,
    EExprToken.EX_SetConst: EX_SetConst,
    EExprToken.EX_EndSetConst: EX_EndSetConst,
    EExprToken.EX_ArrayGetByRef: EX_ArrayGetByRef,
    # Structs
    EExprToken.EX_StructConst: EX_StructConst,
    EExprToken.EX_EndStructConst: EX_EndStructConst,
    EExprToken.EX_BitFieldConst: EX_BitFieldConst,
    EExprToken.EX_PropertyConst: EX_PropertyConst,
    # Delegates
    EExprToken.EX_AddMulticastDelegate: EX_AddMulticastDelegate,
    EExprToken.EX_ClearMulticastDelegate: EX_ClearMulticastDelegate,
    EExprToken.EX_BindDelegate: EX_BindDelegate,
    EExprToken.EX_RemoveMulticastDelegate: EX_RemoveMulticastDelegate,
    # Jump/control
    EExprToken.EX_Skip: EX_Skip,
    EExprToken.EX_ComputedJump: EX_ComputedJump,
    EExprToken.EX_PushExecutionFlow: EX_PushExecutionFlow,
    EExprToken.EX_PopExecutionFlow: EX_PopExecutionFlow,
    EExprToken.EX_PopExecutionFlowIfNot: EX_PopExecutionFlowIfNot,
    EExprToken.EX_SkipOffsetConst: EX_SkipOffsetConst,
    # Special
    EExprToken.EX_SwitchValue: EX_SwitchValue,
    EExprToken.EX_InstrumentationEvent: EX_InstrumentationEvent,
    EExprToken.EX_FieldPathConst: EX_FieldPathConst,
    # Game-specific opcodes (placeholder — tolerant mode skips unknown data)
    EExprToken.EX_6E: EX_Unknown6E,
    EExprToken.EX_6F: EX_Unknown6F,
    # Sentinel: EX_Max (0xFF) treated as end-of-script marker
    EExprToken.EX_Max: EX_MaxSentinel,
    # RTFM
    EExprToken.EX_AutoRtfmTransact: EX_AutoRtfmTransact,
    EExprToken.EX_AutoRtfmStopTransact: EX_AutoRtfmStopTransact,
    EExprToken.EX_AutoRtfmAbortIfNot: EX_AutoRtfmAbortIfNot,
}

__all__ = [
    "EXPR_CLASS_MAP",
    "FKismetSwitchCase",
    "EX_VariableBase", "EX_LocalVariable", "EX_InstanceVariable",
    "EX_DefaultVariable", "EX_LocalOutVariable", "EX_ClassSparseDataVariable",
    "EX_IntConst", "EX_FloatConst", "EX_ByteConst", "EX_IntConstByte",
    "EX_Int64Const", "EX_UInt64Const", "EX_DoubleConst",
    "EX_IntZero", "EX_IntOne", "EX_True", "EX_False",
    "EX_StringConst", "EX_UnicodeStringConst", "EX_TextConst", "EX_SoftObjectConst",
    "EX_VectorConst", "EX_RotationConst", "EX_TransformConst", "EX_Vector3fConst",
    "EX_Jump", "EX_JumpIfNot", "EX_Skip", "EX_ComputedJump",
    "EX_PushExecutionFlow", "EX_PopExecutionFlow", "EX_PopExecutionFlowIfNot",
    "EX_EndOfScript", "EX_SkipOffsetConst",
    "EX_Let", "EX_LetBase", "EX_LetBool", "EX_LetDelegate",
    "EX_LetMulticastDelegate", "EX_LetObj", "EX_LetWeakObjPtr",
    "EX_LetValueOnPersistentFrame",
    "EX_EndParmValue", "EX_EndFunctionParms", "EX_FinalFunction",
    "EX_CallMath", "EX_LocalFinalFunction", "EX_VirtualFunction",
    "EX_LocalVirtualFunction", "EX_CallMulticastDelegate",
    "EX_CastBase", "EX_Cast", "EX_MetaCast", "EX_DynamicCast",
    "EX_ObjToInterfaceCast", "EX_CrossInterfaceCast", "EX_InterfaceToObjCast",
    "EX_Context", "EX_Context_FailSilent", "EX_ClassContext",
    "EX_InterfaceContext", "EX_StructMemberContext",
    "EX_SetArray", "EX_EndArray", "EX_SetMap", "EX_EndMap",
    "EX_SetSet", "EX_EndSet", "EX_ArrayConst", "EX_EndArrayConst",
    "EX_MapConst", "EX_EndMapConst", "EX_SetConst", "EX_EndSetConst",
    "EX_ArrayGetByRef",
    "EX_StructConst", "EX_EndStructConst", "EX_BitFieldConst", "EX_PropertyConst",
    "EX_AddMulticastDelegate", "EX_ClearMulticastDelegate", "EX_BindDelegate",
    "EX_RemoveMulticastDelegate", "EX_InstanceDelegate",
    "EX_Return", "EX_Assert", "EX_Nothing", "EX_NothingInt32",
    "EX_Self", "EX_NoObject", "EX_NoInterface", "EX_SwitchValue",
    "EX_InstrumentationEvent", "EX_DeprecatedOp4A", "EX_Breakpoint",
    "EX_Tracepoint", "EX_WireTracepoint", "EX_FieldPathConst",
    "EX_ObjectConst", "EX_NameConst",
    "EX_AutoRtfmTransact", "EX_AutoRtfmStopTransact", "EX_AutoRtfmAbortIfNot",
]
