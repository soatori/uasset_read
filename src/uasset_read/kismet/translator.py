from __future__ import annotations

"""
Kismet Expression → C++ Pseudocode Translator.

Translates KismetExpression AST into readable C++ pseudocode.

Provides:
- KismetTranslator: Central dispatcher with line_cpp() for all expression types
"""

import logging
from typing import TYPE_CHECKING

from uasset_read.kismet.expressions.assignments import (
    EX_Let,
    EX_LetBase,
    EX_LetBool,
    EX_LetDelegate,
    EX_LetMulticastDelegate,
    EX_LetObj,
    EX_LetWeakObjPtr,
    EX_LetValueOnPersistentFrame,
)
from uasset_read.kismet.expressions.casts import (
    EX_Cast,
    EX_MetaCast,
    EX_DynamicCast,
    EX_ObjToInterfaceCast,
    EX_CrossInterfaceCast,
    EX_InterfaceToObjCast,
)
from uasset_read.kismet.expressions.containers import (
    EX_SetArray,
    EX_EndArray,
    EX_SetMap,
    EX_EndMap,
    EX_SetSet,
    EX_EndSet,
    EX_ArrayConst,
    EX_EndArrayConst,
    EX_MapConst,
    EX_EndMapConst,
    EX_SetConst,
    EX_EndSetConst,
    EX_ArrayGetByRef,
)
from uasset_read.kismet.expressions.context import (
    EX_Context,
    EX_Context_FailSilent,
    EX_ClassContext,
    EX_InterfaceContext,
    EX_StructMemberContext,
)
from uasset_read.kismet.expressions.control_flow import (
    EX_Jump,
    EX_JumpIfNot,
    EX_Skip,
    EX_ComputedJump,
    EX_PushExecutionFlow,
    EX_PopExecutionFlow,
    EX_PopExecutionFlowIfNot,
    EX_EndOfScript,
    EX_SkipOffsetConst,
)
from uasset_read.kismet.expressions.delegates import (
    EX_AddMulticastDelegate,
    EX_ClearMulticastDelegate,
    EX_BindDelegate,
    EX_RemoveMulticastDelegate,
    EX_InstanceDelegate,
)
from uasset_read.kismet.expressions.functions import (
    EX_EndParmValue,
    EX_EndFunctionParms,
    EX_FinalFunction,
    EX_CallMath,
    EX_LocalFinalFunction,
    EX_VirtualFunction,
    EX_LocalVirtualFunction,
    EX_CallMulticastDelegate,
)
from uasset_read.kismet.expressions.literals import (
    EX_IntConst,
    EX_FloatConst,
    EX_ByteConst,
    EX_IntConstByte,
    EX_Int64Const,
    EX_UInt64Const,
    EX_DoubleConst,
    EX_IntZero,
    EX_IntOne,
    EX_True,
    EX_False,
    EX_NoObject,
    EX_NoInterface,
    EX_Self,
    EX_Nothing,
)
from uasset_read.kismet.expressions.rtfm import (
    EX_AutoRtfmTransact,
    EX_AutoRtfmStopTransact,
    EX_AutoRtfmAbortIfNot,
)
from uasset_read.kismet.expressions.special import (
    EX_Return,
    EX_Assert,
    EX_NothingInt32,
    EX_SwitchValue,
    EX_InstrumentationEvent,
    EX_DeprecatedOp4A,
    EX_Breakpoint,
    EX_Tracepoint,
    EX_WireTracepoint,
    EX_FieldPathConst,
    EX_ObjectConst,
    EX_NameConst,
)
from uasset_read.kismet.expressions.string_consts import (
    EX_StringConst,
    EX_UnicodeStringConst,
    EX_TextConst,
    EX_SoftObjectConst,
)
from uasset_read.kismet.expressions.structs import (
    EX_StructConst,
    EX_EndStructConst,
    EX_BitFieldConst,
    EX_PropertyConst,
)
from uasset_read.kismet.expressions.variables import (
    EX_LocalVariable,
    EX_InstanceVariable,
    EX_DefaultVariable,
    EX_LocalOutVariable,
    EX_ClassSparseDataVariable,
)
from uasset_read.kismet.expressions.vector_consts import (
    EX_VectorConst,
    EX_RotationConst,
    EX_TransformConst,
    EX_Vector3fConst,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.kismet.jump_analyzer import JumpAnalyzer

# ===========================================================================

# ===========================================================================
# KismetTranslator — central line_cpp() dispatcher
# ===========================================================================


class KismetTranslator:
    """
    Translates a single KismetExpression to a one-line C++ pseudocode string.

    Uses match/case dispatch aligned with GetLineExpression switch.
    """

    def __init__(
        self,
        expressions: list["KismetExpression"] | None = None,
    ):
        self._jump_analyzer: "JumpAnalyzer | None" = None
        self._structured_indices: set[int] = set()
        if expressions is not None:
            from uasset_read.kismet.jump_analyzer import JumpAnalyzer

            self._jump_analyzer = JumpAnalyzer(expressions)
            self._structured_indices = self._jump_analyzer.get_structured_indices()

    def line_cpp(self, expr: KismetExpression, index: int | None = None) -> str:
        """Translate a single KismetExpression to C++ pseudocode.

        Dispatches to category-specific _translate_* methods.
        """
        # Try each category in order; first match wins
        for handler in (
            self._translate_variables,
            self._translate_literals,
            self._translate_special,
            self._translate_return,
            self._translate_jumps,
            self._translate_casts,
            self._translate_context,
            self._translate_assignments,
            self._translate_functions,
            self._translate_containers,
            self._translate_structs,
            self._translate_delegates,
            self._translate_misc,
        ):
            result = handler(expr, index)
            if result is not None:
                return result
        return f"/* unknown: {type(expr).__name__} */"

    # -----------------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------------

    def _collect_params(self, expr: KismetExpression) -> list[str]:
        """Collect and translate expression parameters into a list of C++ strings."""
        params: list[str] = []
        if hasattr(expr, "Parameters") and expr.Parameters:  # type: ignore[attr-defined]
            for param in expr.Parameters:  # type: ignore[attr-defined]
                p_str = self.line_cpp(param)
                if p_str:
                    params.append(p_str)
        return params

    def _translate_member(self, expr: KismetExpression, attr: str, fallback: str = "?") -> str:
        """Translate a single member attribute, returning *fallback* if missing or falsy."""
        value = getattr(expr, attr, None)
        if value:
            return self.line_cpp(value)
        return fallback

    # -----------------------------------------------------------------------
    # Category translators — each returns str if handled, None otherwise
    # -----------------------------------------------------------------------

    def _translate_variables(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Variable references: Local / Instance / Default / LocalOut / SparseData."""

        if isinstance(
            expr,
            (
                EX_LocalVariable,
                EX_InstanceVariable,
                EX_DefaultVariable,
                EX_LocalOutVariable,
                EX_ClassSparseDataVariable,
            ),
        ):
            var_ptr = expr.Variable
            if var_ptr is None:
                return "?"
            try:
                return str(var_ptr)
            except (TypeError, ValueError):
                return "?"
        return None

    def _translate_literals(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Literals: Int / Float / Byte / Bool / String / Object / Name / Vector."""

        # --- Integer literals ---
        if isinstance(expr, EX_IntConst):
            val = expr.Value
            if val > 0xFFFFFF and (val & 0xFFFFFF) == 0:
                return f"/* suspicious: 0x{val:08X} */"
            return str(val)
        if isinstance(expr, EX_IntZero):
            return "0"
        if isinstance(expr, EX_IntOne):
            return "1"
        if isinstance(expr, EX_Int64Const):
            return f"{expr.Value}LL"
        if isinstance(expr, EX_UInt64Const):
            return f"{expr.Value}ULL"
        # --- Float/Double ---
        if isinstance(expr, EX_FloatConst):
            return f"{expr.Value}f"
        if isinstance(expr, EX_DoubleConst):
            return str(expr.Value)
        # --- Byte ---
        if isinstance(expr, EX_ByteConst):
            return f"0x{expr.Value:02X}"
        if isinstance(expr, EX_IntConstByte):
            return str(expr.Value)
        # --- Boolean ---
        if isinstance(expr, EX_True):
            return "true"
        if isinstance(expr, EX_False):
            return "false"
        # --- String constants ---
        if isinstance(expr, (EX_StringConst, EX_UnicodeStringConst)):
            val = str(expr.Value).replace("\r\n", "\\n").replace("\n", "\\n").replace('"', '\\"')
            return f'"{val}"'
        if isinstance(expr, EX_TextConst):
            # The member is Text: FScriptText. The old "Value" guard never matched, and
            # FScriptText has no .Text either, so the inner fallback was dead too: every
            # FText constant collapsed to FText("") and lost the source string.
            script_text = expr.Text
            if script_text is not None and script_text.SourceString:
                val = str(script_text.SourceString).replace("\r\n", "\\n").replace("\n", "\\n").replace('"', '\\"')
                return f'FText("{val}")'
            return 'FText("")'
        # --- Object / Name ---
        if isinstance(expr, EX_ObjectConst):
            pkg_index = str(expr.Value) if expr.Value else ""
            if "'" in pkg_index:
                parts = pkg_index.split("'", 1)
                type_name = parts[0]
                path = parts[1].rstrip("'")
                class_pkg = f"U{type_name}"
                return f'FindObject<{class_pkg}>(nullptr, "{path}")'
            return f'FindObject<UObject>(nullptr, "{pkg_index}")'
        if isinstance(expr, EX_NameConst):
            val = str(expr.Value) if expr.Value else ""
            return f'FName("{val}")'
        if isinstance(expr, EX_SoftObjectConst):
            # Member is SoftObject, not Value; the old guard was always False, so this
            # always emitted FSoftObjectPath("").
            inner = self.line_cpp(expr.SoftObject) if expr.SoftObject else '""'
            return f"FSoftObjectPath({inner})"
        # --- Vector / Rotation / Transform ---
        # These expressions inherit from KismetExpression (not KismetExpressionT),
        # fields are directly X/Y/Z etc., not accessed via Value property.
        if isinstance(expr, EX_Vector3fConst):
            return f"FVector3f({expr.X}, {expr.Y}, {expr.Z})"
        if isinstance(expr, EX_VectorConst):
            return f"FVector({expr.X}, {expr.Y}, {expr.Z})"
        if isinstance(expr, EX_RotationConst):
            return f"FRotator({expr.Pitch}, {expr.Yaw}, {expr.Roll})"
        if isinstance(expr, EX_TransformConst):
            return (
                f"FTransform(FQuat({expr.X}, {expr.Y}, "
                f"{expr.Z}, {expr.W}), "
                f"FVector({expr.Pitch}, {expr.Yaw}, "
                f"{expr.Roll}), "
                f"FVector({expr.SX}, {expr.SY}, {expr.SZ}))"
            )
        return None

    def _translate_special(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Special keywords: Self / Nothing / EndOfScript / RTFM."""

        if isinstance(expr, EX_Self):
            return "this"
        if isinstance(expr, (EX_NoObject, EX_NoInterface)):
            return "nullptr"
        if isinstance(
            expr,
            (
                EX_Nothing,
                EX_NothingInt32,
                EX_EndOfScript,
                EX_EndFunctionParms,
                EX_EndParmValue,
                EX_EndArray,
                EX_EndArrayConst,
                EX_EndMap,
                EX_EndMapConst,
                EX_EndSet,
                EX_EndSetConst,
                EX_EndStructConst,
                EX_PushExecutionFlow,
            ),
        ):
            return ""
        # RTFM
        if isinstance(expr, EX_AutoRtfmTransact):
            return "/* RTFM: begin transaction */"
        if isinstance(expr, EX_AutoRtfmStopTransact):
            return "/* RTFM: end transaction */"
        if isinstance(expr, EX_AutoRtfmAbortIfNot):
            return "/* RTFM: abort if condition */"
        return None

    def _translate_return(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """EX_Return."""

        if isinstance(expr, EX_Return):
            ret_expr = expr.ReturnExpression if hasattr(expr, "ReturnExpression") else getattr(expr, "Value", None)
            if ret_expr is None:
                return "return"
            if isinstance(ret_expr, (EX_Nothing, EX_NothingInt32)):
                return "return"
            return f"return {self.line_cpp(ret_expr)}"
        return None

    def _translate_jumps(
        self,
        expr: KismetExpression,
        index: int | None,
    ) -> str | None:
        """Jump / execution flow control: JumpIfNot / Jump / ComputedJump / Skip / Pop."""

        if isinstance(expr, EX_JumpIfNot):
            cond = self._translate_member(expr, "BooleanExpression")
            offset = expr.CodeOffset if hasattr(expr, "CodeOffset") else getattr(expr, "Value", 0)
            if self._jump_analyzer is not None and index is not None:
                if self._jump_analyzer.detect_for_pattern(index) is not None:
                    return f"for ({cond}) {{"
                if self._jump_analyzer.detect_while_pattern(index) is not None:
                    return f"while ({cond}) {{"
                if self._jump_analyzer.detect_if_else_pattern(index) is not None:
                    return f"if ({cond}) {{"
            return f"if (!{cond}) goto Label_{offset};"
        if isinstance(expr, EX_Jump):
            offset = expr.CodeOffset if hasattr(expr, "CodeOffset") else getattr(expr, "Value", 0)
            if self._jump_analyzer is not None and index is not None:
                if self._jump_analyzer.is_while_backjump(index):
                    return ""
            return f"goto Label_{offset};"
        if isinstance(expr, EX_ComputedJump):
            var = self._translate_member(expr, "CodeOffsetExpression")
            return f"goto {var};"
        if isinstance(expr, EX_Skip):
            # EX_Skip extends EX_Jump, so CodeOffset always exists; it has no Value
            # member, making the old else-branch an AttributeError waiting to happen.
            return f"goto Label_{expr.CodeOffset};"
        if isinstance(expr, EX_SkipOffsetConst):
            offset = expr.Value if hasattr(expr, "Value") else 0
            return f"goto Label_{offset};"
        if isinstance(expr, EX_PopExecutionFlow):
            if self._jump_analyzer is not None and index is not None:
                if index in self._structured_indices:
                    return "}"
            return "return;"
        if isinstance(expr, EX_PopExecutionFlowIfNot):
            bool_expr = expr.BooleanExpression
            cond = self.line_cpp(bool_expr) if bool_expr is not None else "?"
            return f"if (!{cond}) return;"
        return None

    def _translate_casts(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Type conversion: Cast / MetaCast / DynamicCast, etc."""

        if isinstance(expr, EX_Cast):
            cast_target = expr.Target
            target = self.line_cpp(cast_target) if cast_target is not None else "?"
            from uasset_read.kismet.tokens import ECastToken

            conversion = getattr(expr, "ConversionType", None)
            type_map = {
                ECastToken.CST_ObjectToInterface: "Interface",
                ECastToken.CST_ObjectToBool: "bool",
                ECastToken.CST_ObjectToBool2: "bool",
                ECastToken.CST_InterfaceToBool: "bool",
                ECastToken.CST_InterfaceToBool2: "bool",
                ECastToken.CST_DoubleToFloat: "float",
                ECastToken.CST_FloatToDouble: "double",
            }
            cpp_type = type_map.get(conversion, "auto") if conversion is not None else "auto"
            return f"static_cast<{cpp_type}>({target})"
        if isinstance(
            expr,
            (
                EX_MetaCast,
                EX_DynamicCast,
                EX_ObjToInterfaceCast,
                EX_CrossInterfaceCast,
                EX_InterfaceToObjCast,
            ),
        ):
            target = self._translate_member(expr, "Target")
            class_ptr = getattr(expr, "ClassPtr", None)
            if class_ptr and hasattr(class_ptr, "Name"):
                class_name = str(class_ptr.Name)
                if not class_name.startswith(("U", "A", "F", "I")):
                    class_name = f"U{class_name}"
            else:
                class_name = "UObject"
            return f"Cast<{class_name}>({target})"
        return None

    def _translate_context(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Context expressions: Context / ClassContext / InterfaceContext / StructMemberContext."""

        if isinstance(expr, (EX_Context, EX_Context_FailSilent)):
            obj = (
                self.line_cpp(expr.ObjectExpression)
                if hasattr(expr, "ObjectExpression") and expr.ObjectExpression
                else "?"
            )
            ctx_expr = (
                self.line_cpp(expr.ContextExpression)
                if hasattr(expr, "ContextExpression") and expr.ContextExpression
                else ""
            )
            func_name = ctx_expr.split("::")[-1] if "::" in ctx_expr else ctx_expr
            if isinstance(expr, EX_Context_FailSilent):
                return f"if ({obj}) {obj}->{func_name}"
            return f"{obj}->{func_name}"
        if isinstance(expr, EX_ClassContext):
            obj = (
                self.line_cpp(expr.ObjectExpression)
                if hasattr(expr, "ObjectExpression") and expr.ObjectExpression
                else "?"
            )
            ctx_expr = (
                self.line_cpp(expr.ContextExpression)
                if hasattr(expr, "ContextExpression") and expr.ContextExpression
                else ""
            )
            func_name = ctx_expr.split("::")[-1] if "::" in ctx_expr else ctx_expr
            return f"{obj}->{func_name}"
        if isinstance(expr, EX_InterfaceContext):
            return (
                self.line_cpp(expr.InterfaceValue) if hasattr(expr, "InterfaceValue") and expr.InterfaceValue else "?"
            )
        if isinstance(expr, EX_StructMemberContext):
            prop = str(expr.Property) if hasattr(expr, "Property") else "?"
            struct = (
                self.line_cpp(expr.StructExpression)
                if hasattr(expr, "StructExpression") and expr.StructExpression
                else "?"
            )
            return f"{struct}.{prop}"
        return None

    def _translate_assignments(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Assignment: Let / LetBool / LetObj / LetValueOnPersistentFrame, etc."""

        if isinstance(
            expr,
            (
                EX_Let,
                EX_LetBase,
                EX_LetBool,
                EX_LetDelegate,
                EX_LetObj,
                EX_LetWeakObjPtr,
                EX_LetMulticastDelegate,
            ),
        ):
            var = self.line_cpp(expr.Variable) if hasattr(expr, "Variable") and expr.Variable else "?"
            assignment = self.line_cpp(expr.Assignment) if hasattr(expr, "Assignment") and expr.Assignment else "?"
            return f"{var} = {assignment}"
        if isinstance(expr, EX_LetValueOnPersistentFrame):
            assignment = (
                self.line_cpp(expr.AssignmentExpression)
                if hasattr(expr, "AssignmentExpression") and expr.AssignmentExpression
                else "?"
            )
            dest = str(expr.DestinationProperty) if hasattr(expr, "DestinationProperty") else "?"
            var_name = f"UberGraphFrame->{dest}" if "K2Node_" in dest else dest
            return f"{var_name} = {assignment}"
        return None

    def _translate_functions(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Function calls: FinalFunction / CallMath / VirtualFunction / CallMulticastDelegate."""

        if isinstance(expr, (EX_FinalFunction, EX_CallMath)):
            params_list = []
            if hasattr(expr, "Parameters") and expr.Parameters:
                for param in expr.Parameters:
                    p_str = self.line_cpp(param)
                    if p_str:
                        params_list.append(p_str)
            stack_node = getattr(expr, "StackNode", 0)
            if isinstance(expr, EX_CallMath):
                cn = f"Function_{stack_node}" if isinstance(stack_node, int) else str(stack_node)
                return f"{cn}::Call_{stack_node}({', '.join(params_list)})"
            if isinstance(expr, EX_LocalFinalFunction):
                return f"LocalFunction_{stack_node}({', '.join(params_list)})"
            return f"Function_{stack_node}({', '.join(params_list)})"
        if isinstance(expr, (EX_VirtualFunction, EX_LocalVirtualFunction)):
            virtual_name = getattr(expr, "VirtualFunctionName", "?")
            # VirtualFunctionName is a plain str today; getattr keeps the FText-shaped
            # fallback without asserting a .Text member the declared type does not have.
            func_name = str(getattr(virtual_name, "Text", virtual_name))
            params_list = []
            if hasattr(expr, "Parameters") and expr.Parameters:
                for param in expr.Parameters:
                    p_str = self.line_cpp(param)
                    if p_str:
                        params_list.append(p_str)
            return f"{func_name}({', '.join(params_list)})"
        if isinstance(expr, EX_CallMulticastDelegate):
            params_list = []
            if hasattr(expr, "Parameters") and expr.Parameters:
                for param in expr.Parameters:
                    p_str = self.line_cpp(param)
                    if p_str:
                        params_list.append(p_str)
            delegate = self.line_cpp(expr.Delegate) if hasattr(expr, "Delegate") and expr.Delegate else "?"
            return f"{delegate}->Broadcast({', '.join(params_list)})"
        if isinstance(expr, EX_InstanceDelegate):
            fn = getattr(expr, "FunctionName", "?")
            return f'"{fn}"'
        return None

    def _translate_containers(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Containers: SetArray / ArrayConst / SetMap / MapConst / SetSet / SetConst / ArrayGetByRef."""

        if isinstance(expr, EX_SetArray):
            var = (
                self.line_cpp(expr.AssigningProperty)
                if hasattr(expr, "AssigningProperty") and expr.AssigningProperty
                else "?"
            )
            values = [v for el in (expr.Elements or []) if (v := self.line_cpp(el))]
            return f"{var} = [{', '.join(values)}]"
        if isinstance(expr, EX_ArrayConst):
            values = [v for el in (expr.Elements or []) if (v := self.line_cpp(el))]
            inner_type = str(expr.InnerProperty) if hasattr(expr, "InnerProperty") and expr.InnerProperty else "auto"
            return f"TArray<{inner_type}>{{{', '.join(values)}}}"
        if isinstance(expr, EX_SetMap):
            target = self.line_cpp(expr.MapProperty) if hasattr(expr, "MapProperty") and expr.MapProperty else "?"
            if not hasattr(expr, "Elements") or not expr.Elements:
                return f"{target} = TMap {{ }}"
            pairs = self._extract_map_pairs(expr.Elements)
            return f"{target} = TMap {{ {', '.join(pairs)} }}"
        if isinstance(expr, EX_MapConst):
            if not hasattr(expr, "Elements") or not expr.Elements:
                return "TMap { }"
            pairs = self._extract_map_pairs(expr.Elements)
            return f"TMap {{ {', '.join(pairs)} }}"
        if isinstance(expr, EX_SetSet):
            target = self.line_cpp(expr.SetProperty) if hasattr(expr, "SetProperty") and expr.SetProperty else "?"
            values = [v for el in (expr.Elements or []) if (v := self.line_cpp(el))]
            return f"{target} = TSet{{{', '.join(values)}}}"
        if isinstance(expr, EX_SetConst):
            values = [v for el in (expr.Elements or []) if (v := self.line_cpp(el))]
            return f"TSet{{{', '.join(values)}}}"
        if isinstance(expr, EX_ArrayGetByRef):
            arr = self.line_cpp(expr.ArrayVariable) if hasattr(expr, "ArrayVariable") and expr.ArrayVariable else "?"
            idx = self.line_cpp(expr.ArrayIndex) if hasattr(expr, "ArrayIndex") and expr.ArrayIndex else "?"
            return f"{arr}[{idx}]"
        return None

    def _translate_structs(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Struct constants / bit fields / property constants."""

        if isinstance(expr, EX_StructConst):
            struct_name = str(getattr(expr.Struct, "Name", "Struct"))
            values = [v for prop in (expr.Properties or []) if (v := self.line_cpp(prop))]
            return f"F{struct_name}{{{', '.join(values)}}}"
        if isinstance(expr, EX_BitFieldConst):
            return str(expr.ConstValue) if hasattr(expr, "ConstValue") else "0"
        if isinstance(expr, EX_PropertyConst):
            return str(expr.Property) if hasattr(expr, "Property") else "?"
        return None

    def _translate_delegates(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """Delegate operations: Add / Clear / Bind / Remove multicast delegate."""

        if isinstance(expr, EX_AddMulticastDelegate):
            delegate = self.line_cpp(expr.Delegate) if hasattr(expr, "Delegate") and expr.Delegate else "?"
            to_add = self.line_cpp(expr.DelegateToAdd) if hasattr(expr, "DelegateToAdd") and expr.DelegateToAdd else "?"
            return f"{delegate}->Add({to_add})"
        if isinstance(expr, EX_ClearMulticastDelegate):
            delegate = (
                self.line_cpp(expr.DelegateToClear)
                if hasattr(expr, "DelegateToClear") and expr.DelegateToClear
                else "?"
            )
            return f"{delegate}.Clear()"
        if isinstance(expr, EX_BindDelegate):
            delegate = self.line_cpp(expr.Delegate) if hasattr(expr, "Delegate") and expr.Delegate else "?"
            obj = self.line_cpp(expr.ObjectTerm) if hasattr(expr, "ObjectTerm") and expr.ObjectTerm else "?"
            fn = str(getattr(expr.FunctionName, "Text", "?"))
            return f'{delegate}->BindUFunction({obj}, FName("{fn}"))'
        if isinstance(expr, EX_RemoveMulticastDelegate):
            delegate = self.line_cpp(expr.Delegate) if hasattr(expr, "Delegate") and expr.Delegate else "?"
            to_remove = (
                self.line_cpp(expr.DelegateToRemove)
                if hasattr(expr, "DelegateToRemove") and expr.DelegateToRemove
                else "?"
            )
            sep = (
                "->"
                if isinstance(expr.Delegate, (EX_Context, EX_Context_FailSilent))
                else "."
                if hasattr(expr, "Delegate") and expr.Delegate
                else "."
            )
            return f"{delegate}{sep}RemoveDelegate({to_remove})"
        return None

    def _translate_misc(
        self,
        expr: KismetExpression,
        _index: int | None,
    ) -> str | None:
        """SwitchValue / Assert / Deprecated / Breakpoint / FieldPath."""

        if isinstance(expr, EX_SwitchValue):
            idx_term = expr.IndexTerm
            idx = self.line_cpp(idx_term) if idx_term else "?"
            # Cases is Optional now that the field annotation matches its None default;
            # binding once keeps a None from reaching len()/iteration.
            cases = expr.Cases or []
            if len(cases) == 2:
                case0_term, case1_term = cases[0].CaseTerm, cases[1].CaseTerm
                case0 = self.line_cpp(case0_term) if case0_term is not None else "?"
                case1 = self.line_cpp(case1_term) if case1_term is not None else "?"
                return f"{idx} ? {case1} : {case0}"
            lines = [f"switch ({idx}) {{"]
            for case_item in cases:
                index_term = case_item.CaseIndexValueTerm
                case_idx = self.line_cpp(index_term) if index_term is not None else "?"
                case_term = case_item.CaseTerm
                case_val = self.line_cpp(case_term) if case_term is not None else "?"
                lines.append(f"  case {case_idx}: return {case_val}; break;")
            default_term = expr.DefaultTerm
            default = self.line_cpp(default_term) if default_term else "?"
            lines.append(f"  default: return {default};")
            lines.append("}")
            return "\n".join(lines)
        if isinstance(expr, EX_Assert):
            cond = str(expr.AssertExpression) if hasattr(expr, "AssertExpression") else "?"
            return f"assert({cond})"
        if isinstance(expr, EX_DeprecatedOp4A):
            return ""
        if isinstance(expr, (EX_Breakpoint, EX_Tracepoint, EX_WireTracepoint)):
            return ""
        if isinstance(expr, EX_InstrumentationEvent):
            return ""
        if isinstance(expr, EX_FieldPathConst):
            return str(expr.Value) if hasattr(expr, "Value") else "?"
        return None

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _extract_map_pairs(self, elements: list) -> list[str]:
        """Extract "key: val" string pairs from alternating key-value element list."""
        pairs: list[str] = []
        for i in range(0, len(elements), 2):
            if i + 1 < len(elements):
                key = self.line_cpp(elements[i])
                val = self.line_cpp(elements[i + 1])
                pairs.append(f"{key}: {val}")
        return pairs
