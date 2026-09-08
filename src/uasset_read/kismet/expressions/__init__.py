"""Kismet expression classes and token-to-class mapping.

Re-exports ``EXPR_CLASS_MAP`` from ``_map`` for backward compatibility.
Individual expression classes live in submodules (literals, variables, etc.)
— prefer importing from those in new code.
"""

from uasset_read.kismet.expressions._map import EXPR_CLASS_MAP

# Backward-compatible re-exports (consumed by tests and external code)
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.expressions.literals import (
    EX_IntConst, EX_FloatConst, EX_ByteConst, EX_IntConstByte,
    EX_Int64Const, EX_UInt64Const, EX_DoubleConst,
    EX_IntZero, EX_IntOne, EX_True, EX_False, EX_NoObject, EX_NoInterface, EX_Self, EX_Nothing,
)
from uasset_read.kismet.expressions.variables import (
    EX_LocalVariable, EX_InstanceVariable, EX_DefaultVariable,
    EX_LocalOutVariable, EX_ClassSparseDataVariable,
)
from uasset_read.kismet.expressions.string_consts import (
    EX_StringConst, EX_UnicodeStringConst, EX_TextConst, EX_SoftObjectConst,
)
from uasset_read.kismet.expressions.vector_consts import (
    EX_VectorConst, EX_RotationConst, EX_TransformConst, EX_Vector3fConst,
)
from uasset_read.kismet.expressions.control_flow import (
    EX_Jump, EX_JumpIfNot, EX_Skip, EX_ComputedJump,
    EX_PushExecutionFlow, EX_PopExecutionFlow, EX_PopExecutionFlowIfNot,
    EX_EndOfScript, EX_SkipOffsetConst,
)
from uasset_read.kismet.expressions.assignments import (
    EX_Let, EX_LetBool, EX_LetDelegate, EX_LetMulticastDelegate,
    EX_LetObj, EX_LetWeakObjPtr, EX_LetValueOnPersistentFrame,
)
from uasset_read.kismet.expressions.functions import (
    EX_EndParmValue, EX_EndFunctionParms, EX_FinalFunction, EX_CallMath,
    EX_LocalFinalFunction, EX_VirtualFunction, EX_LocalVirtualFunction, EX_CallMulticastDelegate,
)
from uasset_read.kismet.expressions.casts import (
    EX_Cast, EX_MetaCast, EX_DynamicCast,
    EX_ObjToInterfaceCast, EX_CrossInterfaceCast, EX_InterfaceToObjCast,
)
from uasset_read.kismet.expressions.context import (
    EX_Context, EX_Context_FailSilent, EX_ClassContext, EX_InterfaceContext, EX_StructMemberContext,
)
from uasset_read.kismet.expressions.containers import (
    EX_SetArray, EX_EndArray, EX_SetMap, EX_EndMap, EX_SetSet, EX_EndSet,
    EX_ArrayConst, EX_EndArrayConst, EX_MapConst, EX_EndMapConst,
    EX_SetConst, EX_EndSetConst, EX_ArrayGetByRef,
)
from uasset_read.kismet.expressions.structs import (
    EX_StructConst, EX_EndStructConst, EX_BitFieldConst, EX_PropertyConst,
)
from uasset_read.kismet.expressions.delegates import (
    EX_AddMulticastDelegate, EX_ClearMulticastDelegate, EX_BindDelegate,
    EX_RemoveMulticastDelegate, EX_InstanceDelegate,
)
from uasset_read.kismet.expressions.special import (
    EX_Return, EX_Assert, EX_NothingInt32, EX_SwitchValue,
    EX_InstrumentationEvent, EX_DeprecatedOp4A, EX_Breakpoint, EX_Tracepoint, EX_WireTracepoint,
    EX_FieldPathConst, EX_ObjectConst, EX_NameConst,
)
from uasset_read.kismet.expressions.rtfm import (
    EX_AutoRtfmTransact, EX_AutoRtfmStopTransact, EX_AutoRtfmAbortIfNot,
)

__all__ = [
    "EXPR_CLASS_MAP",
    "KismetExpression",
    # Literals
    "EX_IntConst", "EX_FloatConst", "EX_ByteConst", "EX_IntConstByte",
    "EX_Int64Const", "EX_UInt64Const", "EX_DoubleConst",
    "EX_IntZero", "EX_IntOne", "EX_True", "EX_False",
    "EX_NoObject", "EX_NoInterface", "EX_Self", "EX_Nothing",
    # Variables
    "EX_LocalVariable", "EX_InstanceVariable", "EX_DefaultVariable",
    "EX_LocalOutVariable", "EX_ClassSparseDataVariable",
    # String constants
    "EX_StringConst", "EX_UnicodeStringConst", "EX_TextConst", "EX_SoftObjectConst",
    # Vector constants
    "EX_VectorConst", "EX_RotationConst", "EX_TransformConst", "EX_Vector3fConst",
    # Control flow
    "EX_Jump", "EX_JumpIfNot", "EX_Skip", "EX_ComputedJump",
    "EX_PushExecutionFlow", "EX_PopExecutionFlow", "EX_PopExecutionFlowIfNot",
    "EX_EndOfScript", "EX_SkipOffsetConst",
    # Assignments
    "EX_Let", "EX_LetBool", "EX_LetDelegate", "EX_LetMulticastDelegate",
    "EX_LetObj", "EX_LetWeakObjPtr", "EX_LetValueOnPersistentFrame",
    # Functions
    "EX_EndParmValue", "EX_EndFunctionParms", "EX_FinalFunction", "EX_CallMath",
    "EX_LocalFinalFunction", "EX_VirtualFunction", "EX_LocalVirtualFunction",
    "EX_CallMulticastDelegate",
    # Casts
    "EX_Cast", "EX_MetaCast", "EX_DynamicCast",
    "EX_ObjToInterfaceCast", "EX_CrossInterfaceCast", "EX_InterfaceToObjCast",
    # Context
    "EX_Context", "EX_Context_FailSilent", "EX_ClassContext",
    "EX_InterfaceContext", "EX_StructMemberContext",
    # Containers
    "EX_SetArray", "EX_EndArray", "EX_SetMap", "EX_EndMap",
    "EX_SetSet", "EX_EndSet", "EX_ArrayConst", "EX_EndArrayConst",
    "EX_MapConst", "EX_EndMapConst", "EX_SetConst", "EX_EndSetConst",
    "EX_ArrayGetByRef",
    # Structs
    "EX_StructConst", "EX_EndStructConst", "EX_BitFieldConst", "EX_PropertyConst",
    # Delegates
    "EX_AddMulticastDelegate", "EX_ClearMulticastDelegate", "EX_BindDelegate",
    "EX_RemoveMulticastDelegate", "EX_InstanceDelegate",
    # Special
    "EX_Return", "EX_Assert", "EX_NothingInt32", "EX_SwitchValue",
    "EX_InstrumentationEvent", "EX_DeprecatedOp4A", "EX_Breakpoint",
    "EX_Tracepoint", "EX_WireTracepoint", "EX_FieldPathConst",
    "EX_ObjectConst", "EX_NameConst",
    # RTFM
    "EX_AutoRtfmTransact", "EX_AutoRtfmStopTransact", "EX_AutoRtfmAbortIfNot",
]
