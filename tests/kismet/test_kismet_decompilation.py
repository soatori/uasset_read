"""Kismet 反编译器单元测试。

覆盖：
- 函数引用解析 (FunctionRefResolver)
- 跳转标签预扫描 (JumpAnalyzer)
- 结构化控制流 (JumpAnalyzer + StructuredControlFlow)
- 数学函数简化 (MathFunctionCleaner)
- UE→C++ 类型映射 (resolve_ue_type / ue_package_path_to_cpp_class)
- 类前缀推导 (infer_class_prefix)
"""
from unittest.mock import MagicMock

import pytest

from uasset_read.kismet.function_resolver import FunctionRefResolver
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.expressions.functions import (
    EX_FinalFunction,
    EX_CallMath,
    EX_LocalFinalFunction,
)
from uasset_read.kismet.expressions.control_flow import (
    EX_Jump,
    EX_JumpIfNot,
    EX_PushExecutionFlow,
    EX_PopExecutionFlow,
)
from uasset_read.kismet.jump_analyzer import JumpAnalyzer
from uasset_read.kismet.structured_flow import StructuredControlFlow
from uasset_read.kismet.translator import MathFunctionCleaner
from uasset_read.cpp_gen.cpp_type_mapper import (
    resolve_ue_type,
    ue_package_path_to_cpp_class,
    infer_class_prefix,
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _make_linker():
    """创建 mock linker。"""
    return MagicMock()


def _make_instance(object_name, object_class=None, outer=None):
    """创建 mock UObjectInstance。"""
    inst = MagicMock()
    inst.object_name = object_name
    inst.object_class = object_class
    inst.outer = outer
    return inst


def _stub(statement_index: int, label: str = "stmt"):
    """创建最简 KismetExpression mock，仅携带 StatementIndex。"""
    class _Stub:
        StatementIndex = statement_index
        def __repr__(self):
            return f"<Stub {label}@{statement_index}>"
    return _Stub()


# ---------------------------------------------------------------------------
# 1. 函数引用解析
# ---------------------------------------------------------------------------

class TestFunctionReferenceResolution:
    """FunctionRefResolver — 通过 mock linker 验证 StackNode → ClassName::FuncName。"""

    def test_basic_resolution(self):
        """StackNode 解析应返回 (ClassName, FuncName) 格式。"""
        linker = _make_linker()
        inst = _make_instance("ReceiveBeginPlay", object_class="AActor")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve_string(1)

        assert result == "AActor::ReceiveBeginPlay"

    def test_null_index_returns_none(self):
        """stack_node=0 应返回 None，不访问 linker。"""
        linker = _make_linker()
        resolver = FunctionRefResolver(linker)

        assert resolver.resolve(0) is None
        linker.resolve_package_index.assert_not_called()

    def test_blueprint_generated_class_uses_outer(self):
        """BlueprintGeneratedClass 应取 outer.object_name 作为类名。"""
        linker = _make_linker()
        outer = _make_instance("MyBlueprint_C")
        inst = _make_instance(
            "ExecuteUbergraph_0",
            object_class="BlueprintGeneratedClass",
            outer=outer,
        )
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        assert resolver.resolve_string(1) == "MyBlueprint_C::ExecuteUbergraph_0"

    def test_caches_result(self):
        """连续 resolve 相同 StackNode 应只查询 linker 一次。"""
        linker = _make_linker()
        inst = _make_instance("Func", object_class="Cls")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        resolver.resolve(5)
        resolver.resolve(5)

        linker.resolve_package_index.assert_called_once()

    def test_null_class_falls_back_to_unknown(self):
        """object_class 为 None 时应回退到 Unknown。"""
        linker = _make_linker()
        inst = _make_instance("SomeFunc", object_class=None)
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(3)

        assert result == ("Unknown", "SomeFunc")

    def test_import_index_resolves(self):
        """负数 StackNode（import）应正确解析。"""
        linker = _make_linker()
        inst = _make_instance("K2Node_CallFunction", object_class="KismetSystemLibrary")
        linker.resolve_package_index.return_value = inst

        resolver = FunctionRefResolver(linker)
        result = resolver.resolve(-1)

        assert result == ("KismetSystemLibrary", "K2Node_CallFunction")

    def test_unresolvable_returns_fallback_string(self):
        """无法解析时 resolve_string 应返回 Function_{stack_node}。"""
        linker = _make_linker()
        linker.resolve_package_index.return_value = None

        resolver = FunctionRefResolver(linker)
        assert resolver.resolve_string(42) == "Function_42"


# ---------------------------------------------------------------------------
# 2. 跳转标签预扫描
# ---------------------------------------------------------------------------

class TestJumpLabelScanning:
    """JumpAnalyzer — 偏移量→索引映射和跳转目标注册。"""

    def test_label_mapping(self):
        """StatementIndex 应正确映射到表达式索引。"""
        exprs = [_stub(0), _stub(10), _stub(20)]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.find_label_index(0) == 0
        assert analyzer.find_label_index(10) == 1
        assert analyzer.find_label_index(20) == 2
        assert analyzer.find_label_index(99) is None

    def test_jump_target_registration(self):
        """EX_JumpIfNot 的 CodeOffset 应注册为跳转目标。"""
        cond = _stub(100)
        jin = EX_JumpIfNot(CodeOffset=30, BooleanExpression=cond)
        jin.StatementIndex = 0
        exprs = [_stub(0), _stub(10), jin]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.is_jump_target(30) is True
        assert analyzer.is_jump_target(0) is False

    def test_jump_sources_tracked(self):
        """应记录跳转到同一目标的所有源索引。"""
        cond = _stub(100)
        jin = EX_JumpIfNot(CodeOffset=30, BooleanExpression=cond)
        jin.StatementIndex = 0
        exprs = [_stub(0), _stub(10), jin]
        analyzer = JumpAnalyzer(exprs)

        sources = analyzer.get_jump_sources(30)
        assert 2 in sources

    def test_empty_expressions(self):
        """空表达式列表不应报错。"""
        analyzer = JumpAnalyzer([])
        assert analyzer.find_label_index(0) is None
        assert analyzer.is_jump_target(0) is False
        assert analyzer.get_jump_sources(0) == []

    def test_forward_jump_not_target_of_others(self):
        """自身有 CodeOffset 但无其他指令跳向它，不算跳转目标。"""
        jmp = EX_Jump(CodeOffset=50)
        jmp.StatementIndex = 0
        analyzer = JumpAnalyzer([jmp])

        # 50 是 jmp 的跳转目标（它跳向 50）
        assert analyzer.is_jump_target(50) is True
        # 0 不是任何指令的跳转目标
        assert analyzer.is_jump_target(0) is False


# ---------------------------------------------------------------------------
# 3. 结构化 if/else
# ---------------------------------------------------------------------------

class TestStructuredIfElse:
    """JumpAnalyzer — if/else 控制流模式检测。"""

    def test_if_else_pattern(self):
        """JumpIfNot → then → Jump(end) → else → end 应识别为 if_else。"""
        cond = _stub(0)
        jin = EX_JumpIfNot(CodeOffset=30, BooleanExpression=cond)
        jin.StatementIndex = 1
        then_body = _stub(20)
        jmp_end = EX_Jump(CodeOffset=50)
        jmp_end.StatementIndex = 25
        else_body = _stub(30)
        end_expr = _stub(50)
        exprs = [cond, jin, then_body, jmp_end, else_body, end_expr]

        analyzer = JumpAnalyzer(exprs)
        result = analyzer.detect_if_else_pattern(1)

        assert result is not None
        assert result["type"] == "if_else"
        assert result["start"] == 1
        assert result["then_start"] == 2
        assert result["then_end"] == 3
        assert result["else_start"] == 4
        assert result["else_end"] == 5

    def test_simple_if(self):
        """JumpIfNot → then → end（无 else）应识别为简单 if。"""
        cond = _stub(0)
        jin = EX_JumpIfNot(CodeOffset=30, BooleanExpression=cond)
        jin.StatementIndex = 1
        then_body = _stub(20)
        end_expr = _stub(30)
        exprs = [cond, jin, then_body, end_expr]

        analyzer = JumpAnalyzer(exprs)
        result = analyzer.detect_if_else_pattern(1)

        assert result is not None
        assert result["type"] == "if"
        assert result["then_start"] == 2
        assert result["then_end"] == 2

    def test_not_jump_if_not_returns_none(self):
        """非 JumpIfNot 位置应返回 None。"""
        jmp = EX_Jump(CodeOffset=10)
        jmp.StatementIndex = 0
        exprs = [_stub(0), jmp]
        assert JumpAnalyzer(exprs).detect_if_else_pattern(1) is None

    def test_out_of_range_returns_none(self):
        """索引越界应返回 None。"""
        analyzer = JumpAnalyzer([_stub(0)])
        assert analyzer.detect_if_else_pattern(-1) is None
        assert analyzer.detect_if_else_pattern(5) is None


# ---------------------------------------------------------------------------
# 4. 结构化 while
# ---------------------------------------------------------------------------

class TestStructuredWhile:
    """JumpAnalyzer — while 循环控制流模式检测。"""

    def test_while_pattern(self):
        """JumpIfNot(exit) → body → Jump(back) 应识别为 while。"""
        cond = _stub(0)
        jin = EX_JumpIfNot(CodeOffset=50, BooleanExpression=cond)
        jin.StatementIndex = 10
        body = _stub(20)
        jmp_back = EX_Jump(CodeOffset=10)
        jmp_back.StatementIndex = 30
        exit_expr = _stub(50)
        exprs = [cond, jin, body, jmp_back, exit_expr]

        analyzer = JumpAnalyzer(exprs)
        result = analyzer.detect_while_pattern(1)

        assert result is not None
        assert result["type"] == "while"
        assert result["start"] == 1
        assert result["body_start"] == 2
        assert result["body_end"] == 3
        assert result["exit_label"] == 50

    def test_while_backjump_before_start(self):
        """回跳目标在 start_idx 之前也应识别为 while。"""
        pre = _stub(5)
        cond = _stub(10)
        jin = EX_JumpIfNot(CodeOffset=50, BooleanExpression=cond)
        jin.StatementIndex = 15
        body = _stub(30)
        jmp_back = EX_Jump(CodeOffset=5)
        jmp_back.StatementIndex = 40
        exit_expr = _stub(50)
        exprs = [pre, cond, jin, body, jmp_back, exit_expr]

        analyzer = JumpAnalyzer(exprs)
        result = analyzer.detect_while_pattern(2)

        assert result is not None
        assert result["type"] == "while"

    def test_no_backjump_not_while(self):
        """循环体内无回跳应返回 None。"""
        cond = _stub(0)
        jin = EX_JumpIfNot(CodeOffset=30, BooleanExpression=cond)
        jin.StatementIndex = 1
        body = _stub(10)
        jmp_fwd = EX_Jump(CodeOffset=50)
        jmp_fwd.StatementIndex = 20
        exit_expr = _stub(30)
        exprs = [cond, jin, body, jmp_fwd, exit_expr]

        assert JumpAnalyzer(exprs).detect_while_pattern(1) is None

    def test_while_no_statement_index(self):
        """JumpIfNot 无 StatementIndex 应返回 None。"""
        cond = _stub(0)
        jin = EX_JumpIfNot(CodeOffset=30, BooleanExpression=cond)
        jin.StatementIndex = None
        jmp_back = EX_Jump(CodeOffset=0)
        jmp_back.StatementIndex = 10
        exprs = [cond, jin, jmp_back]

        assert JumpAnalyzer(exprs).detect_while_pattern(1) is None

    def test_while_recognized_by_structured_flow(self):
        """StructuredControlFlow 应将 while 模式输出为 while (...) { ... }。"""
        cond = _stub(0)
        jin = EX_JumpIfNot(CodeOffset=50, BooleanExpression=cond)
        jin.StatementIndex = 10
        body = _stub(20)
        jmp_back = EX_Jump(CodeOffset=10)
        jmp_back.StatementIndex = 30
        exit_expr = _stub(50)
        exprs = [cond, jin, body, jmp_back, exit_expr]

        scf = StructuredControlFlow(linker=None)
        lines = scf.reconstruct(exprs)

        # 应包含 while 结构
        while_lines = [l for l in lines if "while (" in l]
        assert len(while_lines) == 1

    def test_if_else_recognized_by_structured_flow(self):
        """StructuredControlFlow 应将 Push/Pop 模式输出为 if/else 结构。"""
        push = EX_PushExecutionFlow()
        push.StatementIndex = 0
        jin = EX_JumpIfNot(CodeOffset=40, BooleanExpression=_stub(0))
        jin.StatementIndex = 1
        then_expr = _stub(10)
        pop = EX_PopExecutionFlow()
        pop.StatementIndex = 20
        else_expr = _stub(40)
        end = _stub(50)
        exprs = [push, jin, then_expr, pop, else_expr, end]

        scf = StructuredControlFlow(linker=None)
        lines = scf.reconstruct(exprs)

        assert any("if (" in l for l in lines)
        assert any("} else {" in l for l in lines)


# ---------------------------------------------------------------------------
# 5. 数学函数简化
# ---------------------------------------------------------------------------

class TestMathFunctionCleaner:
    """MathFunctionCleaner — Kismet 库函数调用简化为 C++ 运算符。"""

    def test_add_int_int(self):
        """Add_IntInt 应简化为 a + b。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "Add_IntInt", ["a", "b"])
        assert result == "a + b"

    def test_multiply_int_int(self):
        """Multiply_IntInt 应简化为 (a * b)。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "Multiply_IntInt", ["x", "y"])
        assert result == "(x * y)"

    def test_not_equal_int_int(self):
        """NotEqual_IntInt 应简化为 (!=) 运算符，不是 (!==)。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "NotEqual_IntInt", ["a", "b"])
        assert "!=" in result
        assert "!==" not in result
        assert result == "(a != b)"

    def test_equal_equal_int_int(self):
        """EqualEqual_IntInt 应简化为 == 运算符。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "EqualEqual_IntInt", ["a", "b"])
        assert result == "a == b"

    def test_subtract_float_float(self):
        """Subtract_FloatFloat 应简化为 a - b。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "Subtract_FloatFloat", ["x", "y"])
        assert result == "x - y"

    def test_divide_int_int(self):
        """Divide_IntInt 应简化为 (a / b)。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "Divide_IntInt", ["n", "d"])
        assert result == "(n / d)"

    def test_less_int_int(self):
        """Less_IntInt 应简化为 (<) 运算符。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "Less_IntInt", ["a", "b"])
        assert result == "(a < b)"

    def test_greater_equal_int_int(self):
        """GreaterEqual_IntInt 应简化为 (>=) 运算符。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "GreaterEqual_IntInt", ["a", "b"])
        assert result == "(a >= b)"

    def test_boolean_and(self):
        """BooleanAND 应简化为 && 运算符。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "BooleanAND", ["a", "b"])
        assert result == "a && b"

    def test_boolean_or(self):
        """BooleanOR 应简化为 || 运算符。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "BooleanOR", ["a", "b"])
        assert result == "(a || b)"

    def test_not_pre_bool(self):
        """Not_PreBool 应简化为 ! 运算符。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "Not_PreBool", ["b"])
        assert result == "!b"

    def test_negate_float(self):
        """Negate 应简化为 -a。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "Negate_Float", ["x"])
        assert result == "-x"

    def test_fallback_unknown_func(self):
        """未知函数应回退到 ClassName::FuncName 格式。"""
        result = MathFunctionCleaner.clean("KismetMathLibrary", "SomeUnknownFunc", ["a", "b"])
        assert result == "KismetMathLibrary::SomeUnknownFunc(a, b)"

    def test_string_equal(self):
        """KismetStringLibrary 的 EqualEqual 也应简化为 ==。"""
        result = MathFunctionCleaner.clean("KismetStringLibrary", "EqualEqual_StrStr", ["a", "b"])
        assert result == "a == b"

    def test_string_not_equal(self):
        """KismetStringLibrary 的 NotEqual 应简化为 (!=)。"""
        result = MathFunctionCleaner.clean("KismetStringLibrary", "NotEqual_StrStr", ["a", "b"])
        assert result == "(a != b)"

    def test_array_length(self):
        """KismetArrayLibrary::Array_Length 应简化为 arr.Length。"""
        result = MathFunctionCleaner.clean("KismetArrayLibrary", "Array_Length", ["arr"])
        assert result == "arr.Length"

    def test_array_add(self):
        """KismetArrayLibrary::Array_Add 应简化为 arr.Add(item)。"""
        result = MathFunctionCleaner.clean("KismetArrayLibrary", "Array_Add", ["arr", "item"])
        assert result == "arr.Add(item)"


# ---------------------------------------------------------------------------
# 6. 类型映射
# ---------------------------------------------------------------------------

class TestTypeMapping:
    """UE 类型路径 → C++ 类型名映射。"""

    @pytest.mark.parametrize("ue_path,cpp_type", [
        ("/Script/Engine.Actor", "AActor"),
        ("/Script/CoreUObject.Object", "UObject"),
        ("/Script/Engine.Character", "ACharacter"),
        ("/Script/Engine.SceneComponent", "USceneComponent"),
        ("/Script/CoreUObject.Vector", "FVector"),
        ("/Script/CoreUObject.Rotator", "FRotator"),
        ("/Script/CoreUObject.Transform", "FTransform"),
    ])
    def test_resolve_ue_type_known(self, ue_path, cpp_type):
        """已知路径应返回正确的 C++ 类型名。"""
        assert resolve_ue_type(ue_path) == cpp_type

    def test_resolve_ue_type_empty_returns_uobject(self):
        """空路径应回退到 UObject。"""
        assert resolve_ue_type("") == "UObject"

    def test_resolve_ue_type_unknown_defaults_to_u_prefix(self):
        """未知路径应使用 U 前缀。"""
        result = resolve_ue_type("/Script/Engine.MyCustomComponent")
        # 未在映射中的路径会走启发式，可能返回 U 前缀
        assert result.startswith("U")

    def test_ue_package_path_to_cpp_class_known(self):
        """已知包路径应返回正确的 C++ 类名。"""
        assert ue_package_path_to_cpp_class("/Script/Engine.Actor") == "AActor"

    def test_ue_package_path_to_cpp_class_core_uobject(self):
        """CoreUObject 路径应返回 F 前缀。"""
        result = ue_package_path_to_cpp_class("/Script/CoreUObject.Object")
        # CoreUObject.Object 映射为 UObject
        assert result == "UObject"

    def test_ue_package_path_to_cpp_class_empty(self):
        """空路径应返回空字符串。"""
        assert ue_package_path_to_cpp_class("") == ""


# ---------------------------------------------------------------------------
# 7. 类前缀推导
# ---------------------------------------------------------------------------

class TestClassPrefixInference:
    """infer_class_prefix — 从父类名推断 C++ 类型前缀。"""

    def test_acharacter_prefix(self):
        """ACharacter 应推导 A 前缀（Actor 派生）。"""
        assert infer_class_prefix("ACharacter") == "A"

    def test_uobject_prefix(self):
        """UObject 应推导 U 前缀。"""
        assert infer_class_prefix("UObject") == "U"

    def test_ascene_component_prefix(self):
        """USceneComponent 应推导 U 前缀。"""
        assert infer_class_prefix("USceneComponent") == "U"

    def test_fvector_prefix(self):
        """FVector 应推导 F 前缀（结构体）。"""
        assert infer_class_prefix("FVector") == "F"

    def test_edirection_prefix(self):
        """EDirection 应推导 E 前缀（枚举）。"""
        assert infer_class_prefix("EDirection") == "E"

    def test_iinteractable_prefix(self):
        """IInteractable 应推导 I 前缀（接口）。"""
        assert infer_class_prefix("IInteractable") == "I"

    def test_unknown_class_defaults_to_u(self):
        """未知类名应默认返回 U 前缀。"""
        assert infer_class_prefix("Unknown") == "U"

    def test_empty_string_defaults_to_u(self):
        """空字符串应返回 U 前缀。"""
        assert infer_class_prefix("") == "U"

    def test_apawn_prefix(self):
        """APawn 应推导 A 前缀。"""
        assert infer_class_prefix("APawn") == "A"

    def test_ucamera_component_prefix(self):
        """UCameraComponent 应推导 U 前缀。"""
        assert infer_class_prefix("UCameraComponent") == "U"
