"""line_cpp() tests — KismetTranslator for all expression types."""
import pytest
from uasset_read.kismet.tokens import EExprToken, ECastToken
from uasset_read.kismet.translator import KismetTranslator, TypeRegistry, MathFunctionCleaner

# Import real expression classes
from uasset_read.kismet.expressions.variables import (
    EX_LocalVariable, EX_InstanceVariable, EX_DefaultVariable,
)
from uasset_read.kismet.expressions.literals import (
    EX_IntConst, EX_FloatConst, EX_ByteConst, EX_Int64Const,
    EX_IntZero, EX_IntOne, EX_True, EX_False,
)
from uasset_read.kismet.expressions.string_consts import (
    EX_StringConst, EX_UnicodeStringConst, EX_TextConst,
)
from uasset_read.kismet.expressions.special import (
    EX_Return, EX_Nothing, EX_NothingInt32, EX_Self,
    EX_NoObject, EX_NoInterface, EX_SwitchValue,
    EX_DeprecatedOp4A, EX_Assert, EX_ObjectConst, EX_NameConst,
)
from uasset_read.kismet.expressions.control_flow import (
    EX_Jump, EX_JumpIfNot, EX_Skip, EX_PushExecutionFlow,
    EX_PopExecutionFlow, EX_PopExecutionFlowIfNot,
    EX_EndOfScript, EX_SkipOffsetConst,
)
from uasset_read.kismet.expressions.assignments import (
    EX_Let, EX_LetBool,
)
from uasset_read.kismet.expressions.functions import (
    EX_EndFunctionParms, EX_EndParmValue, EX_FinalFunction,
    EX_CallMath, EX_LocalFinalFunction, EX_VirtualFunction,
)
from uasset_read.kismet.expressions.casts import (
    EX_Cast,
)
from uasset_read.kismet.expressions.containers import (
    EX_SetArray, EX_ArrayConst, EX_SetMap, EX_MapConst,
    EX_SetSet, EX_SetConst, EX_ArrayGetByRef,
)
from uasset_read.kismet.expressions.structs import (
    EX_StructConst, EX_BitFieldConst, EX_PropertyConst,
)
from uasset_read.kismet.expressions.delegates import (
    EX_AddMulticastDelegate, EX_ClearMulticastDelegate,
    EX_BindDelegate, EX_RemoveMulticastDelegate,
)
from uasset_read.kismet.expressions.context import (
    EX_StructMemberContext,
)
from uasset_read.kismet.expressions.rtfm import (
    EX_AutoRtfmTransact, EX_AutoRtfmStopTransact, EX_AutoRtfmAbortIfNot,
)
from uasset_read.kismet.expressions.vector_consts import (
    EX_Vector3fConst,
)
from uasset_read.kismet.property_pointer import FKismetPropertyPointer, FFieldPath


# --- Helpers ---

def _make_var(name: str, cls=EX_LocalVariable) -> EX_LocalVariable:
    fp = FKismetPropertyPointer(bNew=True, New=FFieldPath(Path=[name]))
    return cls(Variable=fp)


def _make_return(inner=None):
    return EX_Return(ReturnExpression=inner)


class TestLiterals:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_int_const(self):
        assert self.t.line_cpp(EX_IntConst(Value=42)) == "42"

    def test_int_zero(self):
        assert self.t.line_cpp(EX_IntZero()) == "0"

    def test_int_one(self):
        assert self.t.line_cpp(EX_IntOne()) == "1"

    def test_true(self):
        assert self.t.line_cpp(EX_True()) == "true"

    def test_false(self):
        assert self.t.line_cpp(EX_False()) == "false"

    def test_float_const(self):
        assert self.t.line_cpp(EX_FloatConst(Value=3.14)) == "3.14f"

    def test_int64_const(self):
        assert self.t.line_cpp(EX_Int64Const(Value=123)) == "123LL"

    def test_byte_const(self):
        assert self.t.line_cpp(EX_ByteConst(Value=0xAB)) == "0xAB"

    def test_string_const(self):
        assert self.t.line_cpp(EX_StringConst(Value="hello")) == '"hello"'

    def test_string_const_with_newlines(self):
        assert self.t.line_cpp(EX_StringConst(Value="line1\nline2")) == '"line1\\nline2"'

    def test_string_const_with_quotes(self):
        assert self.t.line_cpp(EX_StringConst(Value='say "hi"')) == '"say \\"hi\\""'

    def test_name_const(self):
        assert self.t.line_cpp(EX_NameConst(Value="MyName")) == 'FName("MyName")'


class TestVariables:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_local_variable(self):
        assert self.t.line_cpp(_make_var("MyVar")) == "MyVar"

    def test_instance_variable(self):
        assert self.t.line_cpp(_make_var("InstanceVar", EX_InstanceVariable)) == "InstanceVar"

    def test_default_variable(self):
        assert self.t.line_cpp(_make_var("DefaultVar", EX_DefaultVariable)) == "DefaultVar"


class TestAssignments:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_let_simple(self):
        expr = EX_Let(Variable=_make_var("x"), Assignment=EX_IntConst(Value=5))
        assert self.t.line_cpp(expr) == "x = 5"

    def test_let_bool(self):
        expr = EX_LetBool(Variable=_make_var("flag"), Assignment=EX_True())
        assert self.t.line_cpp(expr) == "flag = true"


class TestFunctionCalls:
    """Test function call translation.

    Note: StackNode is an int (FPackageIndex). Without linker/import table
    context, function calls use Function_N placeholder format.
    MathFunctionCleaner is tested directly in test_math_cleaner.py.
    """

    def setup_method(self):
        self.t = KismetTranslator()

    def test_call_math_placeholder(self):
        expr = EX_CallMath(
            StackNode=42,
            Parameters=[_make_var("a"), _make_var("b")]
        )
        result = self.t.line_cpp(expr)
        # Without linker, StackNode can't be resolved — uses placeholder
        assert "Function_42" in result

    def test_final_function_placeholder(self):
        expr = EX_FinalFunction(
            StackNode=99,
            Parameters=[_make_var("arg1")]
        )
        assert self.t.line_cpp(expr) == "Function_99(arg1)"

    def test_local_final_function(self):
        expr = EX_LocalFinalFunction(
            StackNode=7,
            Parameters=[_make_var("x")]
        )
        assert self.t.line_cpp(expr) == "LocalFunction_7(x)"

    def test_math_cleaner_direct(self):
        # MathFunctionCleaner is tested in test_math_cleaner.py
        # but verify it integrates properly:
        result = MathFunctionCleaner.clean("KismetMathLibrary", "Add_IntInt", ["a", "b"])
        assert result == "a + b"


class TestReturn:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_return_value(self):
        assert self.t.line_cpp(_make_return(EX_IntConst(Value=42))) == "return 42"

    def test_return_variable(self):
        assert self.t.line_cpp(_make_return(_make_var("result"))) == "return result"

    def test_return_nothing(self):
        assert self.t.line_cpp(_make_return(EX_Nothing())) == "return"


class TestControlFlow:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_jump(self):
        assert self.t.line_cpp(EX_Jump(CodeOffset=100)) == "goto Label_100;"

    def test_jump_if_not(self):
        expr = EX_JumpIfNot(BooleanExpression=_make_var("cond"), CodeOffset=50)
        assert self.t.line_cpp(expr) == "if (!cond) goto Label_50;"

    def test_pop_execution_flow(self):
        assert self.t.line_cpp(EX_PopExecutionFlow()) == "return;"

    def test_pop_if_not(self):
        expr = EX_PopExecutionFlowIfNot(BooleanExpression=_make_var("cond"))
        assert self.t.line_cpp(expr) == "if (!cond) return;"

    def test_skip(self):
        assert self.t.line_cpp(EX_Skip(CodeOffset=200)) == "goto Label_200;"

    def test_end_of_script(self):
        assert self.t.line_cpp(EX_EndOfScript()) == ""

    def test_push_execution_flow(self):
        assert self.t.line_cpp(EX_PushExecutionFlow(PushingAddress=100)) == ""

    def test_skip_offset_const(self):
        assert self.t.line_cpp(EX_SkipOffsetConst(Value=300)) == "goto Label_300;"


class TestSpecial:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_self(self):
        assert self.t.line_cpp(EX_Self()) == "this"

    def test_no_object(self):
        assert self.t.line_cpp(EX_NoObject()) == "nullptr"

    def test_no_interface(self):
        assert self.t.line_cpp(EX_NoInterface()) == "nullptr"

    def test_nothing(self):
        assert self.t.line_cpp(EX_Nothing()) == ""

    def test_nothing_int32(self):
        assert self.t.line_cpp(EX_NothingInt32()) == ""

    def test_deprecated(self):
        assert self.t.line_cpp(EX_DeprecatedOp4A()) == "/* deprecated */"

    def test_assert(self):
        expr = EX_Assert(AssertExpression=_make_var("condition"))
        result = self.t.line_cpp(expr)
        assert "assert(" in result

    def test_end_function_parms(self):
        assert self.t.line_cpp(EX_EndFunctionParms()) == ""

    def test_end_parm_value(self):
        assert self.t.line_cpp(EX_EndParmValue()) == ""

    def test_rtfm_transact(self):
        assert "RTFM" in self.t.line_cpp(EX_AutoRtfmTransact())

    def test_rtfm_stop(self):
        assert "RTFM" in self.t.line_cpp(EX_AutoRtfmStopTransact())

    def test_rtfm_abort(self):
        assert "RTFM" in self.t.line_cpp(EX_AutoRtfmAbortIfNot())


class TestCasts:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_cast_object_to_bool(self):
        expr = EX_Cast(
            Target=_make_var("obj"),
            ConversionType=ECastToken.CST_ObjectToBool
        )
        result = self.t.line_cpp(expr)
        assert "static_cast<bool>" in result

    def test_cast_double_to_float(self):
        expr = EX_Cast(
            Target=_make_var("val"),
            ConversionType=ECastToken.CST_DoubleToFloat
        )
        result = self.t.line_cpp(expr)
        assert "static_cast<float>" in result

    def test_cast_object_to_interface(self):
        expr = EX_Cast(
            Target=_make_var("obj"),
            ConversionType=ECastToken.CST_ObjectToInterface
        )
        result = self.t.line_cpp(expr)
        assert "static_cast<Interface>" in result


class TestContainers:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_array_const(self):
        expr = EX_ArrayConst(
            InnerProperty="int",
            Elements=[EX_IntConst(Value=1), EX_IntConst(Value=2), EX_IntConst(Value=3)]
        )
        result = self.t.line_cpp(expr)
        assert "TArray<int>" in result
        assert "1" in result
        assert "2" in result
        assert "3" in result

    def test_set_const(self):
        expr = EX_SetConst(Elements=[EX_IntConst(Value=1), EX_IntConst(Value=2)])
        result = self.t.line_cpp(expr)
        assert "TSet" in result

    def test_map_const(self):
        expr = EX_MapConst(Elements=[
            EX_StringConst(Value="key1"), EX_IntConst(Value=1),
            EX_StringConst(Value="key2"), EX_IntConst(Value=2),
        ])
        result = self.t.line_cpp(expr)
        assert "TMap" in result
        assert '"key1": 1' in result

    def test_array_get_by_ref(self):
        expr = EX_ArrayGetByRef(
            ArrayVariable=_make_var("arr"),
            ArrayIndex=EX_IntConst(Value=0)
        )
        assert self.t.line_cpp(expr) == "arr[0]"


class TestStructMemberContext:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_struct_member(self):
        fp = FKismetPropertyPointer(bNew=True, New=FFieldPath(Path=["MyField"]))
        expr = EX_StructMemberContext(Property=fp, StructExpression=_make_var("s"))
        assert self.t.line_cpp(expr) == "s.MyField"


class TestDelegates:
    def setup_method(self):
        self.t = KismetTranslator()

    def test_add_multicast_delegate(self):
        expr = EX_AddMulticastDelegate(
            Delegate=_make_var("MyEvent"),
            DelegateToAdd=_make_var("Handler")
        )
        assert self.t.line_cpp(expr) == "MyEvent->Add(Handler)"

    def test_clear_multicast_delegate(self):
        expr = EX_ClearMulticastDelegate(DelegateToClear=_make_var("MyEvent"))
        assert self.t.line_cpp(expr) == "MyEvent.Clear()"
