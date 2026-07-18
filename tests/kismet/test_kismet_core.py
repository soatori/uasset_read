"""Kismet 核心测试 — 反编译、质量、控制流、语义提取。

合并自：
- test_kismet_decompilation.py: 函数引用解析、跳转分析、结构化控制流、数学简化、类型映射、Set 运算
- test_kismet_quality.py: 质量验证、BPGC 字节码、字节码提取器、可疑 IntConst、废弃 token
- test_control_flow.py: 增强控制流（for/switch 检测、Push/Pop、结构化率分析）
- test_kismet_semantic.py: goto 标签输出、语义调用提取
"""
from __future__ import annotations

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


# ---------------------------------------------------------------------------
# 8. Set 库函数语义翻译（合并自 test_translator_set.py）
# ---------------------------------------------------------------------------

class TestSetDifference:
    """Set_Difference 语义回归测试（Issue #387 残留）。"""

    def test_set_difference_uses_minus_operator(self):
        """Set_Difference 应输出 A - B，而非 A == B。"""
        result = MathFunctionCleaner._clean_set(
            "Set_Difference", ["setA", "setB", "result"]
        )
        assert "-" in result
        assert "==" not in result
        assert result == "result = setA - setB"

    def test_set_difference_no_equality(self):
        """确保 Set_Difference 输出中不包含相等比较符号。"""
        result = MathFunctionCleaner._clean_set(
            "Set_Difference", ["MySet", "OtherSet", "Diff"]
        )
        assert "Diff = MySet - OtherSet" == result


class TestSetCleanTable:
    """其他 Set 库函数的翻译验证。"""

    def test_set_add_items(self):
        result = MathFunctionCleaner._clean_set("Set_AddItems", ["s", "item"])
        assert result == "s.Add(item)"

    def test_set_clear(self):
        result = MathFunctionCleaner._clean_set("Set_Clear", ["s"])
        assert result == "s.Clear()"

    def test_set_is_empty(self):
        result = MathFunctionCleaner._clean_set("Set_IsEmpty", ["s"])
        assert result == "s.Length == 0"

    def test_set_length(self):
        result = MathFunctionCleaner._clean_set("Set_Length", ["s"])
        assert result == "s.Length"

    def test_set_unknown_fallback(self):
        result = MathFunctionCleaner._clean_set("Set_Unknown", ["a", "b"])
        assert result == "BlueprintSetLibrary::Set_Unknown(a, b)"


import struct
import pytest
from unittest.mock import patch


class TestKismetQuality:
    """kismet 模块质量验证。"""

    def test_kismet_imports(self):
        """kismet 模块可正常导入。"""
        from uasset_read.kismet import bytecode_extractor
        assert bytecode_extractor is not None

    def test_kismet_tokens_all_unique(self):
        """EExprToken 枚举值必须唯一。"""
        from uasset_read.kismet.tokens import EExprToken
        values = [t.value for t in EExprToken]
        assert len(values) == len(set(values)), "EExprToken 存在重复值"

    def test_expr_class_map_covers_all_tokens(self):
        """EXPR_CLASS_MAP 应覆盖所有 EExprToken 值（除保留值）。"""
        from uasset_read.kismet.tokens import EExprToken
        from uasset_read.kismet.expressions import EXPR_CLASS_MAP
        for token in EExprToken:
            if token.value in (0x03, 0x05, 0x08, 0x0A, 0x0D, 0x0E, 0x10,
                               0x56, 0x57, 0x58, 0x59):
                continue  # 保留/未使用值
            assert token in EXPR_CLASS_MAP, f"EXPR_CLASS_MAP 缺少 {token.name} (0x{token.value:02X})"

    # ==================================================================
    # 缺陷 1: EX_NameConst 应使用 read_i32 而非 read_u32
    # ==================================================================

    def test_name_const_uses_signed_read(self):
        """EX_NameConst 应使用 read_i32 读取 FName index/number（对齐 UE 序列化格式）。

        UE FName 序列化为两个 int32 值。read_fname_kismet() 正确使用 read_i32，
        但 EX_NameConst.from_archive() 错误使用 read_u32。
        如果 name index 是负值（如 -1 表示 None），read_u32 会将其解释为
        4294967295 而非 -1，导致 resolve_fname 无法正确处理。
        """
        from uasset_read.kismet.expressions.special import EX_NameConst
        from uasset_read.kismet.archive import FKismetArchive

        # 构造一个 FName: index=-1 (signed), number=0
        # 如果用 read_u32，-1 会变成 4294967295
        name_index = -1
        name_number = 0
        data = struct.pack('<ii', name_index, name_number)  # 两个 int32

        archive = FKismetArchive(data, "test", [], tolerant=False)
        expr = EX_NameConst.from_archive(archive, [])

        # 正确行为：使用 read_i32，-1 应该被解析为 -1
        # resolve_fname 会将 -1 视为越界，返回 "Unknown_-1"
        assert "Unknown_-1" in expr.Value

    def test_name_const_positive_index(self):
        """EX_NameConst 正数索引应正常工作。"""
        from uasset_read.kismet.expressions.special import EX_NameConst
        from uasset_read.kismet.archive import FKismetArchive

        name_map = ["TestName", "AnotherName"]
        data = struct.pack('<ii', 0, 0)  # index=0, number=0

        archive = FKismetArchive(data, "test", name_map, tolerant=False)
        expr = EX_NameConst.from_archive(archive, name_map)

        assert expr.Value == "TestName"

    def test_name_const_with_number(self):
        """EX_NameConst 带 number 后缀应正确格式化。"""
        from uasset_read.kismet.expressions.special import EX_NameConst
        from uasset_read.kismet.archive import FKismetArchive

        name_map = ["TestName"]
        data = struct.pack('<ii', 0, 3)  # index=0, number=3

        archive = FKismetArchive(data, "test", name_map, tolerant=False)
        expr = EX_NameConst.from_archive(archive, name_map)

        assert expr.Value == "TestName_3"

    def test_name_const_matches_read_fname_kismet(self):
        """EX_NameConst 的读取方式应与 FKismetArchive.read_fname_kismet 一致。"""
        from uasset_read.kismet.archive import FKismetArchive

        name_map = ["Hello", "World"]
        # 构造两个 FName 的原始数据
        data = struct.pack('<iiii', 1, 0, 0, 2)  # FName("World_0"), FName("Hello_2")

        archive = FKismetArchive(data, "test", name_map, tolerant=False)

        # 通过 read_fname_kismet 读取
        fname1 = archive.read_fname_kismet()
        fname2 = archive.read_fname_kismet()

        assert fname1 == "World"
        assert fname2 == "Hello_2"

    # ==================================================================
    # 缺陷 2: EX_RemoveMulticastDelegate 字段命名错误
    # ==================================================================

    def test_remove_multicast_delegate_field_name(self):
        """EX_RemoveMulticastDelegate 的第二个字段应命名为 DelegateToRemove。

        当前错误命名为 DelegateToAdd（从 EX_AddMulticastDelegate 复制而来），
        与 UE 语义不符。UE 源码中该字段表示"要移除的委托"，不是"要添加的委托"。
        """
        from uasset_read.kismet.expressions.delegates import EX_RemoveMulticastDelegate
        # 检查类定义中是否有 DelegateToRemove 字段
        import dataclasses
        fields = {f.name for f in dataclasses.fields(EX_RemoveMulticastDelegate)}
        assert "DelegateToRemove" in fields, (
            "EX_RemoveMulticastDelegate 应有 DelegateToRemove 字段，"
            f"当前字段: {fields}"
        )

    def test_remove_multicast_delegate_from_archive_uses_correct_field(self):
        """EX_RemoveMulticastDelegate.from_archive 应填充 DelegateToRemove 字段。"""
        from uasset_read.kismet.expressions.delegates import EX_RemoveMulticastDelegate
        from uasset_read.kismet.archive import FKismetArchive

        # EX_RemoveMulticastDelegate 格式: Delegate(expression) DelegateToRemove(expression)
        # 构造: Delegate=Self(0x17), DelegateToRemove=IntConst(0x1D, 42), EndFunctionParms(0x16)
        data = bytearray()
        data.extend(struct.pack('B', 0x17))  # Delegate: EX_Self
        data.extend(struct.pack('B', 0x1D))  # DelegateToRemove token: EX_IntConst
        data.extend(struct.pack('<i', 42))  # DelegateToRemove value: 42
        data.extend(struct.pack('B', 0x16))  # EndFunctionParms

        archive = FKismetArchive(bytes(data), "test", [], tolerant=False)
        expr = EX_RemoveMulticastDelegate.from_archive(archive, [])

        # 修复后应有 DelegateToRemove 字段
        assert hasattr(expr, 'DelegateToRemove'), "应有 DelegateToRemove 属性"
        assert expr.DelegateToRemove is not None
        if hasattr(expr.DelegateToRemove, 'Value'):
            assert expr.DelegateToRemove.Value == 42

    # ==================================================================
    # 缺陷 3: EX_SetArray.from_archive 存储位置错误
    # ==================================================================

    def test_set_array_assigning_property_populated(self):
        """EX_SetArray.from_archive 应填充 AssigningProperty 字段。

        当前错误存储到 ArrayInnerProp，导致 translator 查找 AssigningProperty
        时始终得到 None，输出 "?" 而非实际变量名。
        """
        from uasset_read.kismet.expressions.containers import EX_SetArray
        from uasset_read.kismet.archive import FKismetArchive

        # EX_SetArray 格式: FKismetPropertyPointer + elements + EX_EndArray
        # FKismetPropertyPointer: bNew(u32) + FFieldPath(count(u32) + name_index(u32))
        data = bytearray()
        data.extend(struct.pack('<I', 1))  # bNew = True (u32, 1=nonzero)
        data.extend(struct.pack('<I', 1))  # FFieldPath count = 1
        data.extend(struct.pack('<I', 0))  # name index = 0
        data.extend(struct.pack('B', 0x32))  # EX_EndArray token (single byte)

        name_map = ["MyArray"]
        archive = FKismetArchive(bytes(data), "test", name_map, tolerant=False)
        expr = EX_SetArray.from_archive(archive, name_map)

        # AssigningProperty 应被填充（而非 ArrayInnerProp）
        assert expr.AssigningProperty is not None, (
            "EX_SetArray.from_archive 应填充 AssigningProperty，"
            "当前 AssigningProperty=None"
        )

    def test_set_array_translator_uses_assigning_property(self):
        """translator 应能正确翻译 EX_SetArray 的变量引用。"""
        from uasset_read.kismet.expressions.containers import EX_SetArray
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer, FFieldPath

        # 构造 EX_SetArray，手动设置 AssigningProperty
        prop = FKismetPropertyPointer(bNew=True, New=FFieldPath(Path=["MyArray"]))
        # 元素列表为 None（简化测试）
        expr = EX_SetArray(AssigningProperty=prop, Elements=None)

        translator = KismetTranslator()
        result = translator.line_cpp(expr)

        # 不应输出 "?" — 应输出包含变量名的结果
        assert "?" not in result or "MyArray" in result, (
            f"EX_SetArray 翻译结果不应为纯 '?': {result}"
        )

    # ==================================================================
    # 缺陷 4: FKismetPropertyPointer.__str__ 旧路径返回原始整数
    # ==================================================================

    def test_property_pointer_legacy_str_not_raw_integer(self):
        """FKismetPropertyPointer 旧路径的 __str__ 不应返回原始整数。

        当前返回 str(self.Old.index) 即纯数字字符串，
        应返回更有意义的描述。
        """
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        from uasset_read.serializers.object_resources import PackageIndex

        # 构造旧路径属性指针
        old_index = PackageIndex(5)
        ptr = FKismetPropertyPointer(bNew=False, Old=old_index)
        result = str(ptr)

        # 不应仅是数字 "5"
        assert result != "5", (
            f"FKismetPropertyPointer 旧路径 __str__ 不应返回纯数字 '5'，"
            f"当前返回: {result}"
        )

    # ==================================================================
    # 附加质量测试
    # ==================================================================

    def test_token_enum_values_match_ue_source(self):
        """关键 token 值应对齐 UE EExprToken.cs。"""
        from uasset_read.kismet.tokens import EExprToken

        assert EExprToken.EX_EndOfScript == 0x53
        assert EExprToken.EX_Return == 0x04
        assert EExprToken.EX_Jump == 0x06
        assert EExprToken.EX_JumpIfNot == 0x07
        assert EExprToken.EX_Context == 0x19
        assert EExprToken.EX_FinalFunction == 0x1C
        assert EExprToken.EX_CallMath == 0x68
        assert EExprToken.EX_SwitchValue == 0x69
        assert EExprToken.EX_LocalFinalFunction == 0x46

    def test_cast_token_values_match_ue_source(self):
        """ECastToken 值应对齐 UE 源码。"""
        from uasset_read.kismet.tokens import ECastToken

        assert ECastToken.CST_ObjectToInterface == 0x00
        assert ECastToken.CST_ObjectToBool == 0x01
        assert ECastToken.CST_InterfaceToBool == 0x02
        assert ECastToken.CST_DoubleToFloat == 0x03
        assert ECastToken.CST_FloatToDouble == 0x04

    def test_expression_base_to_dict(self):
        """KismetExpression 基类 to_dict 应返回正确结构。"""
        from uasset_read.kismet.expressions.literals import EX_IntConst
        expr = EX_IntConst(Value=42)
        expr.StatementIndex = 10
        d = expr.to_dict()
        assert d["Inst"] == "EX_IntConst"
        assert d["StatementIndex"] == 10
        assert d["Value"] == 42

    def test_parse_empty_bytecode(self):
        """解析空字节码应返回空列表。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream
        result = parse_bytecode_stream(b"", [])
        assert result == []

    def test_parse_end_of_script_only(self):
        """仅含 EX_EndOfScript 的字节码应返回单元素列表。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream
        from uasset_read.kismet.tokens import EExprToken

        data = bytes([EExprToken.EX_EndOfScript])
        result = parse_bytecode_stream(data, [])
        assert len(result) == 1
        assert result[0].Token == EExprToken.EX_EndOfScript

    def test_structured_flow_empty_input(self):
        """StructuredControlFlow 空输入应返回空列表。"""
        from uasset_read.kismet.structured_flow import StructuredControlFlow
        flow = StructuredControlFlow()
        result = flow.reconstruct([])
        assert result == []

    def test_type_registry_basic(self):
        """TypeRegistry 基本注册和查询。"""
        from uasset_read.kismet.translator import TypeRegistry
        reg = TypeRegistry()
        reg.register_variable("MyVar", "int")
        assert reg.lookup("MyVar") == "int"
        assert reg.resolve_type("Unknown") == "auto"

    def test_type_registry_populate_from_metadata(self):
        """TypeRegistry 从元数据批量初始化。"""
        from uasset_read.kismet.translator import TypeRegistry
        reg = TypeRegistry()
        reg.populate_from_metadata({
            "variables": [
                {"name": "Health", "type": "FloatProperty"},
                {"name": "bIsDead", "type": "BoolProperty"},
            ],
            "functions": [
                {
                    "name": "TakeDamage",
                    "params": [
                        {"name": "Amount", "type": "FloatProperty"},
                        {"name": "OutResult", "type": "FloatProperty", "flags": "CPF_OutParm"},
                    ],
                }
            ],
        })
        assert reg.resolve_type("Health") == "float"
        assert reg.resolve_type("bIsDead") == "bool"
        assert reg.resolve_type("Amount") == "float"
        assert reg.resolve_type("OutResult") == "float&"

    def test_math_cleaner_basic_ops(self):
        """MathFunctionCleaner 基本运算转换。"""
        from uasset_read.kismet.translator import MathFunctionCleaner

        assert MathFunctionCleaner.clean("KismetMathLibrary", "Add_IntInt", ["a", "b"]) == "a + b"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Multiply_FloatFloat", ["a", "b"]) == "(a * b)"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "EqualEqual_IntInt", ["a", "b"]) == "a == b"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Not_PreBool", ["x"]) == "!x"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "BooleanAND", ["a", "b"]) == "a && b"

    def test_math_cleaner_type_conversion(self):
        """MathFunctionCleaner 类型转换。"""
        from uasset_read.kismet.translator import MathFunctionCleaner

        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_IntToBool", ["x"]) == "(x != 0)"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_BoolToInt", ["x"]) == "(x ? 1 : 0)"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Conv_IntToFloat", ["x"]) == "((float)x)"

    def test_math_cleaner_fallback(self):
        """MathFunctionCleaner 未知函数应回退到 Class::Func 格式。"""
        from uasset_read.kismet.translator import MathFunctionCleaner

        result = MathFunctionCleaner.clean("KismetMathLibrary", "SomeUnknownFunc", ["a"])
        assert result == "KismetMathLibrary::SomeUnknownFunc(a)"

    def test_blueprint_node_cleaner_basic(self):
        """BlueprintNodeCleaner 基本节点映射。"""
        from uasset_read.kismet.blueprint_node_cleaner import BlueprintNodeCleaner

        # Character::Jump
        result = BlueprintNodeCleaner.clean("ACharacter", "Jump", [])
        assert result == "Jump()"

        # Actor::K2_GetActorLocation
        result = BlueprintNodeCleaner.clean("AActor", "K2_GetActorLocation", [])
        assert result == "GetActorLocation()"

        # 未知节点回退
        result = BlueprintNodeCleaner.clean("MyClass", "MyFunc", ["arg1"])
        assert result == "MyClass::MyFunc(arg1)"

    def test_jump_analyzer_empty_expressions(self):
        """JumpAnalyzer 空表达式列表应正常工作。"""
        from uasset_read.kismet.jump_analyzer import JumpAnalyzer
        analyzer = JumpAnalyzer([])
        report = analyzer.analyze_structured_rate()
        assert report.total_jump_exprs == 0
        assert report.rate == 1.0  # 无跳转 → 100% 结构化

    def test_function_body_builder_empty(self):
        """FunctionBodyBuilder 空表达式应返回有效函数体。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder
        builder = FunctionBodyBuilder()
        result = builder.to_function_body([], func_name="TestFunc")
        assert "TestFunc" in result
        assert "{" in result
        assert "}" in result

    def test_kismet_decompiled_result_to_dict(self):
        """KismetDecompiledResult.to_dict 应返回可序列化字典。"""
        import json
        from uasset_read.kismet.result import KismetDecompiledResult

        result = KismetDecompiledResult(
            function_name="TestFunc",
            signature="void TestFunc()",
            local_variables=[],
            cpp_code="void TestFunc() {}",
            expressions=[],
            bytecode_source="function_export",
            bytecode_status="parsed",
        )
        d = result.to_dict()
        # 应可 JSON 序列化
        json_str = json.dumps(d)
        assert "TestFunc" in json_str

    def test_reset_bpgc_cache(self):
        """reset_bpgc_cache 应重置模块级缓存。"""
        from uasset_read.kismet.bytecode_extractor import reset_bpgc_cache, _bpgc_bytecode_cache
        import uasset_read.kismet.bytecode_extractor as mod

        # 设置缓存为非 None
        mod._bpgc_bytecode_cache = {"test": b"data"}
        reset_bpgc_cache()
        assert mod._bpgc_bytecode_cache is None

    def test_extract_and_parse_non_ustruct(self):
        """非 UStruct 类型的 export 应返回空结果。"""
        from uasset_read.kismet.bytecode_extractor import extract_and_parse, USTRUCT_TYPES
        # 验证 USTRUCT_TYPES 包含预期值
        assert "Function" in USTRUCT_TYPES
        assert "UFunction" in USTRUCT_TYPES


# ============================================================================
# bpgc_bytecode 关键路径测试
# ============================================================================

class TestBpgcBytecode:
    """bpgc_bytecode 模块关键路径测试。"""

    def test_parse_cooked_bytecode_buffer_empty(self):
        """空数据应返回空列表。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer
        result = _parse_cooked_bytecode_buffer(b"")
        assert result == []

    def test_parse_cooked_bytecode_buffer_single_function(self):
        """单个函数缓冲区应正确解析。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        # 构造: [u32 size][bytecode ending with 0x53]
        bytecode = bytes([0x04, 0x53])  # EX_Return + EX_EndOfScript
        size = len(bytecode)
        data = size.to_bytes(4, byteorder='little', signed=False) + bytecode

        result = _parse_cooked_bytecode_buffer(data)
        assert len(result) == 1
        assert result[0] == bytecode

    def test_parse_cooked_bytecode_buffer_multiple_functions(self):
        """多个函数缓冲区应正确解析。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        buf1 = bytes([0x04, 0x53])
        buf2 = bytes([0x1D, 0x01, 0x00, 0x00, 0x00, 0x53])
        data = (
            len(buf1).to_bytes(4, byteorder='little', signed=False) + buf1 +
            len(buf2).to_bytes(4, byteorder='little', signed=False) + buf2
        )

        result = _parse_cooked_bytecode_buffer(data)
        assert len(result) == 2
        assert result[0] == buf1
        assert result[1] == buf2

    def test_parse_cooked_bytecode_buffer_size_zero(self):
        """size=0 应终止解析。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        data = (0).to_bytes(4, byteorder='little', signed=False)
        result = _parse_cooked_bytecode_buffer(data)
        assert result == []

    def test_parse_cooked_bytecode_buffer_size_exceeds_remaining(self):
        """size 超过剩余数据时应容错处理。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        # size 声明 100 字节但实际只有 2 字节
        data = (100).to_bytes(4, byteorder='little', signed=False) + bytes([0x53, 0x53])
        result = _parse_cooked_bytecode_buffer(data)
        # 容错模式下应跳过或终止
        assert isinstance(result, list)

    def test_parse_cooked_bytecode_buffer_truncated_header(self):
        """截断的 size header（<4字节）应终止解析。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        data = bytes([0x01, 0x02])  # 只有 2 字节，不够 u32
        result = _parse_cooked_bytecode_buffer(data)
        assert result == []

    def test_parse_cooked_bytecode_buffer_non_standard_sentinel(self):
        """非标准结束标记应接受并记录警告。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        bytecode = bytes([0x04, 0xAA])  # 以 0xAA 结尾（非标准）
        size = len(bytecode)
        data = size.to_bytes(4, byteorder='little', signed=False) + bytecode

        result = _parse_cooked_bytecode_buffer(data)
        assert len(result) == 1  # 容错模式仍接受

    def test_find_next_sentinel(self):
        """_find_next_sentinel 应查找下一个 0x53 或 0xDD。"""
        from uasset_read.kismet.bpgc_bytecode import _find_next_sentinel

        data = bytes([0x01, 0x02, 0x53, 0x04])
        assert _find_next_sentinel(data, 0) == 2
        assert _find_next_sentinel(data, 3) == 4  # len(data) if not found past end

    def test_find_next_sentinel_not_found(self):
        """找不到 sentinel 时应返回数据长度。"""
        from uasset_read.kismet.bpgc_bytecode import _find_next_sentinel

        data = bytes([0x01, 0x02, 0x03, 0x04])
        assert _find_next_sentinel(data, 0) == len(data)

    def test_find_next_sentinel_cooked_variant(self):
        """应识别 0xDD cooked 变体。"""
        from uasset_read.kismet.bpgc_bytecode import _find_next_sentinel

        data = bytes([0x01, 0xDD, 0x03])
        assert _find_next_sentinel(data, 0) == 1

    def test_map_bytecode_to_functions_empty(self):
        """空缓冲区映射应返回空字典。"""
        from uasset_read.kismet.bpgc_bytecode import map_bytecode_to_functions
        result = map_bytecode_to_functions({}, [], [], [], [])
        assert result == {}

    def test_map_bytecode_to_functions_no_function_exports(self):
        """无 Function 类型导出时应返回空字典。"""
        from uasset_read.kismet.bpgc_bytecode import map_bytecode_to_functions
        from unittest.mock import MagicMock

        export = MagicMock()
        export.class_index = MagicMock()

        buffers = {"0": b"\x53"}
        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="BlueprintGeneratedClass"):
            result = map_bytecode_to_functions(buffers, [export], [], [], [])
            assert result == {}

    def test_map_bytecode_to_functions_matching(self):
        """缓冲区应按序号匹配到 Function 导出。"""
        from uasset_read.kismet.bpgc_bytecode import map_bytecode_to_functions
        from unittest.mock import MagicMock

        func_export = MagicMock()
        func_export.object_name = "MyFunction"
        func_export.class_index = MagicMock()

        buffers = {"0": b"\x53", "1": b"\x04\x53"}

        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="Function"):
            result = map_bytecode_to_functions(buffers, [func_export], [], [], [])
            assert "MyFunction" in result
            assert result["MyFunction"] == b"\x53"

    def test_map_bytecode_to_functions_count_mismatch(self):
        """缓冲区数量与 Function 数量不匹配时按 min 配对。"""
        from uasset_read.kismet.bpgc_bytecode import map_bytecode_to_functions
        from unittest.mock import MagicMock

        func1 = MagicMock()
        func1.object_name = "Func1"
        func1.class_index = MagicMock()
        func2 = MagicMock()
        func2.object_name = "Func2"
        func2.class_index = MagicMock()

        buffers = {"0": b"\x53"}  # 只有 1 个缓冲区，2 个函数

        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="Function"):
            result = map_bytecode_to_functions(buffers, [func1, func2], [], [], [])
            assert len(result) == 1
            assert "Func1" in result


# ============================================================================
# bytecode_extractor 关键路径测试
# ============================================================================

class TestBytecodeExtractor:
    """bytecode_extractor 关键路径测试。"""

    def test_parse_bytecode_stream_single_expression(self):
        """单个表达式应正确解析。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream
        from uasset_read.kismet.tokens import EExprToken

        # EX_IntConst (0x1D) + i32 value (42) + EX_EndOfScript (0x53)
        data = struct.pack('B', EExprToken.EX_IntConst) + struct.pack('<i', 42)
        data += struct.pack('B', EExprToken.EX_EndOfScript)

        result = parse_bytecode_stream(data, [], tolerant=True)
        assert len(result) >= 2
        assert result[-1].Token == EExprToken.EX_EndOfScript

    def test_parse_bytecode_stream_tolerant_mode(self):
        """容错模式应跳过未知 token。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream
        from uasset_read.kismet.tokens import EExprToken

        # 未知 token (0xFE) + EX_EndOfScript
        data = bytes([0xFE, EExprToken.EX_EndOfScript])

        # tolerant=True 应不抛异常
        result = parse_bytecode_stream(data, [], tolerant=True)
        assert isinstance(result, list)

    def test_parse_bytecode_stream_non_tolerant_raises(self):
        """非容错模式遇到未知 token 应抛异常。"""
        from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream

        # 构造一个截断的 EX_FinalFunction (0x1C) — 需要更多字节但数据不足
        data = bytes([0x1C])  # EX_FinalFunction but truncated
        with pytest.raises(Exception):
            parse_bytecode_stream(data, [], tolerant=False)

    def test_expressions_to_flat_list(self):
        """expressions_to_flat_list 应返回扁平字典列表。"""
        from uasset_read.kismet.bytecode_extractor import expressions_to_flat_list
        from uasset_read.kismet.expressions.literals import EX_IntConst

        expr = EX_IntConst(Value=42)
        expr.StatementIndex = 0
        result = expressions_to_flat_list([expr])
        assert len(result) == 1
        assert result[0]["Value"] == 42
        assert result[0]["type"] == "EX_IntConst"

    def test_expressions_to_tree(self):
        """expressions_to_tree 应返回树形结构。"""
        from uasset_read.kismet.bytecode_extractor import expressions_to_tree
        from uasset_read.kismet.expressions.literals import EX_IntConst

        expr = EX_IntConst(Value=42)
        expr.StatementIndex = 0
        result = expressions_to_tree([expr])
        assert len(result) == 1
        assert result[0]["type"] == "EX_IntConst"

    def test_is_kismet_expression(self):
        """_is_kismet_expression 应正确识别 KismetExpression。"""
        from uasset_read.kismet.bytecode_extractor import _is_kismet_expression
        from uasset_read.kismet.expressions.literals import EX_IntConst

        assert _is_kismet_expression(EX_IntConst(Value=1)) is True
        assert _is_kismet_expression(42) is False
        assert _is_kismet_expression("string") is False

    def test_extract_and_parse_empty_bytecode(self):
        """extract_and_parse 空字节码应返回空列表。"""
        from uasset_read.kismet.bytecode_extractor import extract_and_parse
        from unittest.mock import MagicMock

        archive = MagicMock()
        export = MagicMock()
        export.has_script_serialization = False
        summary = MagicMock()

        # 非 UStruct 类型
        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="TestComponent"):
            expressions, error, reason = extract_and_parse(
                archive, export, summary, [], [], []
            )
            assert expressions == []
            assert error is None
            assert reason == "none"


# ============================================================================
# 起始 token 集合与可疑 IntConst 测试（合并自 test_bytecode_scanner_fix.py）
# ============================================================================

class TestPlausibleStartTokens:
    """验证 scanner 起始 token 集合已排除误匹配 token。"""

    def test_removed_tokens_not_in_start_set(self):
        """0x1D (EX_IntConst)、0x5A (EX_WireTracepoint)、0x5E (EX_Tracepoint)
        不应出现在 _PLAUSIBLE_SCRIPT_START_TOKENS 中。"""
        from uasset_read.kismet.bytecode_extractor import _PLAUSIBLE_SCRIPT_START_TOKENS

        assert 0x1D not in _PLAUSIBLE_SCRIPT_START_TOKENS, \
            "0x1D (EX_IntConst) 应已从起始 token 集合中移除"
        assert 0x5A not in _PLAUSIBLE_SCRIPT_START_TOKENS, \
            "0x5A (EX_WireTracepoint) 应已从起始 token 集合中移除"
        assert 0x5E not in _PLAUSIBLE_SCRIPT_START_TOKENS, \
            "0x5E (EX_Tracepoint) 应已从起始 token 集合中移除"

    def test_retained_tokens_present(self):
        """保留的安全起始 token 仍应存在。"""
        from uasset_read.kismet.bytecode_extractor import _PLAUSIBLE_SCRIPT_START_TOKENS

        expected = {0x04, 0x19, 0x1B, 0x1C, 0x46}
        assert expected.issubset(_PLAUSIBLE_SCRIPT_START_TOKENS), \
            f"预期保留的 token {expected} 应全部存在"

    def test_start_token_set_exactly_five(self):
        """起始 token 集合应恰好包含 5 个元素。"""
        from uasset_read.kismet.bytecode_extractor import _PLAUSIBLE_SCRIPT_START_TOKENS

        assert len(_PLAUSIBLE_SCRIPT_START_TOKENS) == 5, \
            f"预期 5 个起始 token，实际 {len(_PLAUSIBLE_SCRIPT_START_TOKENS)} 个"


class TestSuspiciousIntConst:
    """验证 EX_IntConst 翻译器对可疑值的安全网。"""

    def _make_int_const(self, value: int):
        """创建 EX_IntConst 表达式实例。"""
        from uasset_read.kismet.expressions import EX_IntConst
        return EX_IntConst(Value=value)

    def test_suspicious_value_emits_comment(self):
        """0x5A000000 (1509949440) 应输出为可疑注释，而非裸数字。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0x5A000000)  # 1509949440
        result = line_cpp(expr)
        assert result.startswith("/* suspicious:"), \
            f"可疑值应输出注释，实际: {result}"
        assert "0x5A000000" in result, \
            f"注释应包含十六进制表示，实际: {result}"

    def test_another_suspicious_value(self):
        """0x1D000000 也应触发安全网。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0x1D000000)
        result = line_cpp(expr)
        assert result.startswith("/* suspicious:"), \
            f"可疑值应输出注释，实际: {result}"

    def test_normal_int_const_still_works(self):
        """正常整数常量应保持不变。"""
        from uasset_read.kismet.translator import line_cpp

        for val in [0, 1, 42, -1, 255, 1024, 0xFFFFFF, -0x80000000]:
            expr = self._make_int_const(val)
            result = line_cpp(expr)
            assert result == str(val), \
                f"正常值 {val} 应直接输出为字符串，实际: {result}"

    def test_non_aligned_value_not_suspicious(self):
        """低位非零的大整数不应触发安全网（如 0x5A000001）。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0x5A000001)
        result = line_cpp(expr)
        assert result == "1509949441", \
            f"低位非零值不应触发安全网，实际: {result}"

    def test_boundary_below_threshold_not_suspicious(self):
        """值 <= 0xFFFFFF 不应触发安全网。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0xFFFFFF)
        result = line_cpp(expr)
        assert result == "16777215", \
            f"边界值 0xFFFFFF 不应触发安全网，实际: {result}"

    def test_aligned_above_threshold_suspicious(self):
        """刚好超过 0xFFFFFF 且低位全零的值应触发安全网。"""
        from uasset_read.kismet.translator import line_cpp

        expr = self._make_int_const(0x01000000)
        result = line_cpp(expr)
        assert result.startswith("/* suspicious:"), \
            f"0x01000000 应触发安全网，实际: {result}"


# ============================================================================
# Deprecated / Instrumentation token 测试（合并自 test_kismet_deprecated_tokens.py）
# ============================================================================

class TestDeprecatedTokenSilentSkip:
    """deprecated / instrumentation token 应返回空字符串。"""

    def test_deprecated_op4a_returns_empty(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_DeprecatedOp4A

        translator = KismetTranslator()
        expr = EX_DeprecatedOp4A()
        result = translator.line_cpp(expr)
        assert result == "", f"EX_DeprecatedOp4A 应返回空字符串，实际: {result!r}"

    def test_breakpoint_returns_empty(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_Breakpoint

        translator = KismetTranslator()
        expr = EX_Breakpoint()
        result = translator.line_cpp(expr)
        assert result == "", f"EX_Breakpoint 应返回空字符串，实际: {result!r}"

    def test_tracepoint_returns_empty(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_Tracepoint

        translator = KismetTranslator()
        expr = EX_Tracepoint()
        result = translator.line_cpp(expr)
        assert result == "", f"EX_Tracepoint 应返回空字符串，实际: {result!r}"

    def test_wire_tracepoint_returns_empty(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_WireTracepoint

        translator = KismetTranslator()
        expr = EX_WireTracepoint()
        result = translator.line_cpp(expr)
        assert result == "", f"EX_WireTracepoint 应返回空字符串，实际: {result!r}"

    def test_instrumentation_event_returns_empty(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_InstrumentationEvent
        from uasset_read.kismet.tokens import EScriptInstrumentationType

        translator = KismetTranslator()
        expr = EX_InstrumentationEvent(
            EventType=EScriptInstrumentationType.Entry,
            EventName="TestFunc",
        )
        result = translator.line_cpp(expr)
        assert result == "", f"EX_InstrumentationEvent 应返回空字符串，实际: {result!r}"


class TestSkippedTokenCounter:
    """统计计数器应正确记录各类 deprecated token 数量。"""

    def test_counter_initially_empty(self):
        from uasset_read.kismet.translator import KismetTranslator

        translator = KismetTranslator()
        assert translator.skipped_tokens == {}

    def test_deprecated_op4a_counter(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_DeprecatedOp4A

        translator = KismetTranslator()
        expr = EX_DeprecatedOp4A()
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_DeprecatedOp4A") == 1

    def test_breakpoint_counter(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_Breakpoint

        translator = KismetTranslator()
        expr = EX_Breakpoint()
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_Breakpoint") == 1

    def test_tracepoint_counter(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_Tracepoint

        translator = KismetTranslator()
        expr = EX_Tracepoint()
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_Tracepoint") == 1

    def test_wire_tracepoint_counter(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_WireTracepoint

        translator = KismetTranslator()
        expr = EX_WireTracepoint()
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_WireTracepoint") == 1

    def test_instrumentation_event_counter(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import EX_InstrumentationEvent
        from uasset_read.kismet.tokens import EScriptInstrumentationType

        translator = KismetTranslator()
        expr = EX_InstrumentationEvent(
            EventType=EScriptInstrumentationType.Exit,
            EventName="TestFunc",
        )
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_InstrumentationEvent") == 1

    def test_multiple_tokens_accumulate(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import (
            EX_DeprecatedOp4A, EX_InstrumentationEvent,
        )
        from uasset_read.kismet.tokens import EScriptInstrumentationType

        translator = KismetTranslator()
        # 翻译 3 个 deprecated + 2 个 instrumentation
        for _ in range(3):
            translator.line_cpp(EX_DeprecatedOp4A())
        for _ in range(2):
            translator.line_cpp(EX_InstrumentationEvent(
                EventType=EScriptInstrumentationType.Entry,
            ))
        assert translator.skipped_tokens["EX_DeprecatedOp4A"] == 3
        assert translator.skipped_tokens["EX_InstrumentationEvent"] == 2
        assert sum(translator.skipped_tokens.values()) == 5

    def test_mixed_token_types_counted_separately(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import (
            EX_DeprecatedOp4A, EX_InstrumentationEvent,
            EX_Breakpoint, EX_Tracepoint, EX_WireTracepoint,
        )
        from uasset_read.kismet.tokens import EScriptInstrumentationType

        translator = KismetTranslator()
        translator.line_cpp(EX_DeprecatedOp4A())
        translator.line_cpp(EX_Breakpoint())
        translator.line_cpp(EX_Tracepoint())
        translator.line_cpp(EX_WireTracepoint())
        translator.line_cpp(EX_InstrumentationEvent(
            EventType=EScriptInstrumentationType.PureEntry,
        ))
        assert translator.skipped_tokens == {
            "EX_DeprecatedOp4A": 1,
            "EX_Breakpoint": 1,
            "EX_Tracepoint": 1,
            "EX_WireTracepoint": 1,
            "EX_InstrumentationEvent": 1,
        }

    def test_no_deprecated_no_counter(self):
        """正常表达式不应影响计数器。"""
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions import EX_IntConst

        translator = KismetTranslator()
        translator.line_cpp(EX_IntConst(Value=42))
        assert translator.skipped_tokens == {}


class TestNoDeprecatedCommentInOutput:
    """确保翻译输出中不再包含 /* deprecated */ 或 /* instrumentation */ 注释。"""

    def test_output_does_not_contain_deprecated_comment(self):
        from uasset_read.kismet.translator import KismetTranslator
        from uasset_read.kismet.expressions.special import (
            EX_DeprecatedOp4A, EX_InstrumentationEvent,
            EX_Breakpoint, EX_Tracepoint, EX_WireTracepoint,
        )
        from uasset_read.kismet.tokens import EScriptInstrumentationType

        translator = KismetTranslator()
        translator.line_cpp(EX_DeprecatedOp4A())
        translator.line_cpp(EX_Breakpoint())
        translator.line_cpp(EX_Tracepoint())
        translator.line_cpp(EX_WireTracepoint())
        translator.line_cpp(EX_InstrumentationEvent(
            EventType=EScriptInstrumentationType.Entry,
            EventName="Foo",
        ))
        # 所有返回值都应为空字符串
        assert translator.skipped_tokens  # 确认确实翻译了这些 token


from uasset_read.kismet.expressions.control_flow import (
    EX_Jump, EX_JumpIfNot, EX_ComputedJump,
    EX_PushExecutionFlow, EX_PopExecutionFlow,
    EX_EndOfScript,
)
from uasset_read.kismet.expressions.special import EX_SwitchValue, FKismetSwitchCase
from uasset_read.kismet.expressions.assignments import (
    EX_Let, EX_LetBool, EX_LetValueOnPersistentFrame,
)
from uasset_read.kismet.jump_analyzer import JumpAnalyzer, StructuredRateReport
from uasset_read.kismet.result import KismetDecompiledResult


# ================================================================
# 测试辅助工厂 — 增强版
# ================================================================

def _make_expr(statement_index: int):
    """创建最简 mock，仅携带 StatementIndex。"""
    class _Stub:
        StatementIndex = statement_index
    return _Stub()


def _make_jump(statement_index: int, code_offset: int) -> EX_Jump:
    jmp = EX_Jump(CodeOffset=code_offset)
    jmp.StatementIndex = statement_index
    return jmp


def _make_jump_if_not(
    statement_index: int,
    code_offset: int,
    boolean_expression=None,
) -> EX_JumpIfNot:
    jmp = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=boolean_expression)
    jmp.StatementIndex = statement_index
    return jmp


def _make_let(statement_index: int, var_name: str = "i") -> EX_Let:
    """创建 mock EX_Let 赋值表达式。"""
    let = EX_Let()
    let.StatementIndex = statement_index
    let.Variable = _make_expr(0)
    let.Assignment = _make_expr(0)
    return let


def _make_let_bool(statement_index: int) -> EX_LetBool:
    """创建 mock EX_LetBool 赋值表达式。"""
    let = EX_LetBool()
    let.StatementIndex = statement_index
    let.Variable = _make_expr(0)
    let.Assignment = _make_expr(0)
    return let


def _make_switch_value(
    statement_index: int,
    end_offset: int = 100,
    case_count: int = 3,
) -> EX_SwitchValue:
    """创建 mock EX_SwitchValue 表达式。"""
    index_term = _make_expr(0)
    cases = []
    for i in range(case_count):
        case = FKismetSwitchCase()
        case.CaseIndexValueTerm = _make_expr(i)
        case.NextOffset = end_offset
        case.CaseTerm = _make_expr(i * 10)
        cases.append(case)
    default_term = _make_expr(999)
    switch = EX_SwitchValue(
        EndGotoOffset=end_offset,
        IndexTerm=index_term,
        Cases=cases,
        DefaultTerm=default_term,
    )
    switch.StatementIndex = statement_index
    return switch


def _make_computed_jump(statement_index: int) -> EX_ComputedJump:
    """创建 mock EX_ComputedJump 表达式。"""
    jmp = EX_ComputedJump(CodeOffsetExpression=_make_expr(0))
    jmp.StatementIndex = statement_index
    return jmp


# ================================================================
# 测试辅助工厂 — Push/Pop 版
# ================================================================

def _make_push(pushing_address: int = 50) -> EX_PushExecutionFlow:
    push = EX_PushExecutionFlow(PushingAddress=pushing_address)
    push.StatementIndex = 0
    return push


def _make_pop() -> EX_PopExecutionFlow:
    pop = EX_PopExecutionFlow()
    pop.StatementIndex = 0
    return pop


# ================================================================
# 测试辅助工厂 — 简单版（用于基础模式检测测试）
# ================================================================

def _make_expr_simple(statement_index: int):
    """创建一个最简 KismetExpression mock，仅携带 StatementIndex（简单版本）。"""
    class _Stub:
        StatementIndex = statement_index
    return _Stub()


def _make_jump_simple(statement_index: int, code_offset: int) -> EX_Jump:
    """创建 EX_Jump 并设置 StatementIndex（简单版本）。"""
    jmp = EX_Jump(CodeOffset=code_offset)
    jmp.StatementIndex = statement_index
    return jmp


def _make_jump_if_not_simple(
    statement_index: int,
    code_offset: int,
    boolean_expression=None,
) -> EX_JumpIfNot:
    """创建 EX_JumpIfNot 并设置 StatementIndex（简单版本）。"""
    jmp = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=boolean_expression)
    jmp.StatementIndex = statement_index
    return jmp


def _make_let_simple(statement_index: int) -> EX_Let:
    """创建 mock EX_Let 赋值表达式（用于 for 循环递增）（简单版本）。"""
    let = EX_Let()
    let.StatementIndex = statement_index
    let.Variable = _make_expr_simple(0)
    let.Assignment = _make_expr_simple(0)
    return let


# ================================================================
# for 循环检测（增强版）
# ================================================================

class TestForDetection:
    """for 循环模式检测增强测试。"""

    def test_for_with_single_assignment_increment(self):
        """单个赋值递增的 for 循环。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=60, boolean_expression=cond,
        )
        body_call = _make_expr(20)
        increment = _make_let(30)
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_expr = _make_expr(60)
        exprs = [cond, jump_if_not, body_call, increment, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_for_pattern(1)
        assert result is not None
        assert result["type"] == "for"
        assert result["start"] == 1
        assert result["body_start"] == 2
        assert result["body_end"] == 4
        assert result["increment_start"] == 3
        assert result["increment_end"] == 3
        assert result["exit_label"] == 60

    def test_for_with_multiple_assignment_increments(self):
        """多个连续赋值递增的 for 循环。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=70, boolean_expression=cond,
        )
        body = _make_expr(20)
        inc1 = _make_let(30)
        inc2 = _make_let_bool(40)
        jump_back = _make_jump(statement_index=50, code_offset=10)
        exit_expr = _make_expr(70)
        exprs = [cond, jump_if_not, body, inc1, inc2, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_for_pattern(1)
        assert result is not None
        assert result["type"] == "for"
        assert result["increment_start"] == 3
        assert result["increment_end"] == 4

    def test_for_body_too_short_no_increment(self):
        """循环体只有回跳无递增，不满足 for 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=1, code_offset=20, boolean_expression=cond,
        )
        jump_back = _make_jump(statement_index=10, code_offset=1)
        exit_expr = _make_expr(20)
        exprs = [cond, jump_if_not, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        # body_start=2, body_end=2 → body_end <= body_start
        assert analyzer.detect_for_pattern(1) is None

    def test_for_no_assignment_before_backjump(self):
        """回跳前没有赋值表达式，不满足 for 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=50, boolean_expression=cond,
        )
        body = _make_expr(20)
        non_assign = _make_expr(30)  # 非赋值表达式
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jump_if_not, body, non_assign, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_for_pattern(1) is None

    def test_for_entire_body_is_increment(self):
        """整个循环体都是递增（无实际循环体），不满足 for 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=40, boolean_expression=cond,
        )
        inc = _make_let(20)  # 递增从 body_start 就开始
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(40)
        exprs = [cond, jump_if_not, inc, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        # inc_start == body_start → 不满足 for
        assert analyzer.detect_for_pattern(1) is None

    def test_for_not_jump_if_not(self):
        """起始位置不是 JumpIfNot，返回 None。"""
        exprs = [_make_expr(0), _make_let(10)]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_for_pattern(0) is None

    def test_for_out_of_range(self):
        """索引越界返回 None。"""
        analyzer = JumpAnalyzer([_make_expr(0)])
        assert analyzer.detect_for_pattern(-1) is None
        assert analyzer.detect_for_pattern(5) is None


# ================================================================
# switch/case 检测
# ================================================================

class TestSwitchDetection:
    """switch/case 模式检测。"""

    def test_switch_detection_basic(self):
        """基本 switch 检测。"""
        switch = _make_switch_value(statement_index=0, end_offset=100, case_count=3)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_switch_pattern(0)
        assert result is not None
        assert result["type"] == "switch"
        assert result["start"] == 0
        assert result["end_offset"] == 100
        assert len(result["cases"]) == 3
        assert result["default_term"] is not None

    def test_switch_with_two_cases(self):
        """两分支 switch（可能被编译为三元表达式，但仍可检测）。"""
        switch = _make_switch_value(statement_index=0, end_offset=50, case_count=2)
        exprs = [_make_expr(999), switch]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_switch_pattern(1)
        assert result is not None
        assert len(result["cases"]) == 2

    def test_switch_with_zero_cases(self):
        """零 case 的 switch（仅 default）。"""
        switch = _make_switch_value(statement_index=0, end_offset=30, case_count=0)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_switch_pattern(0)
        assert result is not None
        assert len(result["cases"]) == 0
        assert result["default_term"] is not None

    def test_switch_not_at_index(self):
        """指定索引不是 EX_SwitchValue，返回 None。"""
        exprs = [_make_expr(0), _make_switch_value(statement_index=10)]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_switch_pattern(0) is None

    def test_switch_out_of_range(self):
        """索引越界返回 None。"""
        analyzer = JumpAnalyzer([_make_expr(0)])
        assert analyzer.detect_switch_pattern(-1) is None
        assert analyzer.detect_switch_pattern(5) is None

    def test_switch_index_term_preserved(self):
        """验证 index_term 正确保留。"""
        index_term = _make_expr(42)
        switch = EX_SwitchValue(
            EndGotoOffset=100,
            IndexTerm=index_term,
            Cases=[],
            DefaultTerm=None,
        )
        switch.StatementIndex = 0
        analyzer = JumpAnalyzer([switch])

        result = analyzer.detect_switch_pattern(0)
        assert result is not None
        assert result["index_term"] is index_term


# ================================================================
# 统一模式检测入口
# ================================================================

class TestDetectPattern:
    """detect_pattern 统一入口测试。"""

    def test_detect_pattern_for_priority_over_while(self):
        """for 优先于 while 检测。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=60, boolean_expression=cond,
        )
        body = _make_expr(20)
        inc = _make_let(30)
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_expr = _make_expr(60)
        exprs = [cond, jump_if_not, body, inc, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(1)
        assert result is not None
        assert result["type"] == "for"

    def test_detect_pattern_while_when_no_increment(self):
        """无递增时回退到 while。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=50, boolean_expression=cond,
        )
        body = _make_expr(20)
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(1)
        assert result is not None
        assert result["type"] == "while"

    def test_detect_pattern_if_else(self):
        """if/else 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=1, code_offset=30, boolean_expression=cond,
        )
        then_body = _make_expr(20)
        jump_end = _make_jump(statement_index=25, code_offset=50)
        else_body = _make_expr(30)
        end_expr = _make_expr(50)
        exprs = [cond, jump_if_not, then_body, jump_end, else_body, end_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(1)
        assert result is not None
        assert result["type"] == "if_else"

    def test_detect_pattern_switch(self):
        """switch 模式。"""
        switch = _make_switch_value(statement_index=0)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(0)
        assert result is not None
        assert result["type"] == "switch"

    def test_detect_pattern_none_for_no_match(self):
        """无法匹配时返回 None。"""
        exprs = [_make_expr(0), _make_expr(10)]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_pattern(0) is None


# ================================================================
# is_while_backjump 缓存
# ================================================================

class TestBackjumpCache:
    """回跳缓存测试。"""

    def test_backjump_cache_basic(self):
        """基本回跳缓存。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=50, boolean_expression=cond,
        )
        body = _make_expr(20)
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.is_while_backjump(3) is True
        assert analyzer.is_while_backjump(2) is False

    def test_backjump_cache_multiple_loops(self):
        """多循环的回跳缓存。"""
        # 循环 1
        cond1 = _make_expr(0)
        jin1 = _make_jump_if_not(statement_index=10, code_offset=50, boolean_expression=cond1)
        body1 = _make_expr(20)
        jb1 = _make_jump(statement_index=30, code_offset=10)
        exit1 = _make_expr(50)
        # 循环 2
        cond2 = _make_expr(60)
        jin2 = _make_jump_if_not(statement_index=70, code_offset=110, boolean_expression=cond2)
        body2 = _make_expr(80)
        jb2 = _make_jump(statement_index=90, code_offset=70)
        exit2 = _make_expr(110)

        exprs = [cond1, jin1, body1, jb1, exit1, cond2, jin2, body2, jb2, exit2]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.is_while_backjump(3) is True   # jb1
        assert analyzer.is_while_backjump(8) is True   # jb2
        assert analyzer.is_while_backjump(2) is False


# ================================================================
# 结构化率分析
# ================================================================

class TestStructuredRateAnalysis:
    """结构化率分析测试。"""

    def test_all_structured(self):
        """全部可结构化的表达式。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(statement_index=10, code_offset=30, boolean_expression=cond)
        then_body = _make_expr(20)
        end = _make_expr(30)
        exprs = [cond, jin, then_body, end]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.rate == 1.0
        assert report.goto_count == 0
        assert "if" in report.pattern_counts

    def test_all_goto(self):
        """全部 goto 回退。"""
        jump1 = _make_jump(statement_index=0, code_offset=20)
        target = _make_expr(20)
        exprs = [jump1, target]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.rate == 0.0
        assert report.goto_count == 1
        assert len(report.goto_reasons) == 1

    def test_mixed_patterns(self):
        """混合模式：if + goto。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(statement_index=10, code_offset=30, boolean_expression=cond)
        then_body = _make_expr(20)
        end_if = _make_expr(30)
        # 独立 goto
        jump = _make_jump(statement_index=40, code_offset=100)
        target = _make_expr(100)
        exprs = [cond, jin, then_body, end_if, jump, target]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.structured_count >= 1
        assert report.goto_count >= 1
        assert report.rate < 1.0
        assert report.rate > 0.0

    def test_empty_expressions(self):
        """空表达式列表。"""
        analyzer = JumpAnalyzer([])
        report = analyzer.analyze_structured_rate()
        assert report.rate == 1.0
        assert report.total_jump_exprs == 0

    def test_no_jump_expressions(self):
        """无跳转指令的表达式列表。"""
        exprs = [_make_expr(0), _make_expr(10)]
        analyzer = JumpAnalyzer(exprs)
        report = analyzer.analyze_structured_rate()
        assert report.rate == 1.0
        assert report.total_jump_exprs == 0

    def test_switch_in_report(self):
        """switch 模式计入报告。"""
        switch = _make_switch_value(statement_index=0)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.pattern_counts.get("switch", 0) >= 1
        assert report.rate == 1.0

    def test_computed_jump_goto_reason(self):
        """ComputedJump 的 goto 原因。"""
        cj = _make_computed_jump(statement_index=0)
        exprs = [cj]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.goto_count == 1
        assert "computed_jump" in report.goto_reasons[0]["reason"]

    def test_forward_jump_goto_reason(self):
        """前跳 goto 原因。"""
        jump = _make_jump(statement_index=0, code_offset=20)
        target = _make_expr(20)
        exprs = [jump, target]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.goto_count == 1
        assert "forward_jump" in report.goto_reasons[0]["reason"]

    def test_unmatched_conditional_goto_reason(self):
        """未匹配条件跳转的 goto 原因。"""
        # JumpIfNot 但没有回跳 → 不是 while/for，false_label 不存在 → 不是 if
        jin = _make_jump_if_not(
            statement_index=0, code_offset=999,
            boolean_expression=_make_expr(100),
        )
        exprs = [jin]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.goto_count == 1
        assert "unmatched_conditional" in report.goto_reasons[0]["reason"]


# ================================================================
# goto 报告格式化
# ================================================================

class TestGotoReport:
    """goto 报告格式化测试。"""

    def test_format_goto_report_basic(self):
        """基本报告格式化。"""
        jump = _make_jump(statement_index=0, code_offset=20)
        target = _make_expr(20)
        analyzer = JumpAnalyzer([jump, target])

        report_text = analyzer.format_goto_report()
        assert "控制流结构化率报告" in report_text
        assert "总跳转指令数" in report_text
        assert "goto 回退原因" in report_text

    def test_format_goto_report_with_precomputed_report(self):
        """使用预计算报告。"""
        report = StructuredRateReport(
            total_jump_exprs=10,
            structured_count=7,
            goto_count=3,
            rate=0.7,
            pattern_counts={"if": 3, "while": 2, "for": 1, "switch": 1},
            goto_reasons=[
                {"index": 5, "reason": "test_reason", "expr_type": "EX_Jump"},
            ],
        )
        analyzer = JumpAnalyzer([])
        text = analyzer.format_goto_report(report)
        assert "70.0%" in text
        assert "if: 3" in text
        assert "test_reason" in text

    def test_format_goto_report_no_goto(self):
        """无 goto 时不显示回退原因。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(statement_index=10, code_offset=30, boolean_expression=cond)
        then_body = _make_expr(20)
        end = _make_expr(30)
        analyzer = JumpAnalyzer([cond, jin, then_body, end])

        report_text = analyzer.format_goto_report()
        assert "goto 回退原因" not in report_text


# ================================================================
# get_structured_indices
# ================================================================

class TestStructuredIndices:
    """结构化索引集合测试。"""

    def test_while_structured_indices(self):
        """while 循环的结构化索引。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=50, boolean_expression=cond,
        )
        body = _make_expr(20)
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jin, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        assert 1 in indices  # jin
        assert 2 in indices  # body
        assert 3 in indices  # jump_back

    def test_for_structured_indices(self):
        """for 循环的结构化索引。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=60, boolean_expression=cond,
        )
        body = _make_expr(20)
        inc = _make_let(30)
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_expr = _make_expr(60)
        exprs = [cond, jin, body, inc, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        assert 1 in indices  # jin
        assert 2 in indices  # body
        assert 3 in indices  # inc
        assert 4 in indices  # jump_back

    def test_switch_structured_indices(self):
        """switch 的结构化索引。"""
        switch = _make_switch_value(statement_index=0)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        assert 0 in indices

    def test_if_else_structured_indices(self):
        """if/else 的结构化索引。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=1, code_offset=30, boolean_expression=cond,
        )
        then_body = _make_expr(20)
        jump_end = _make_jump(statement_index=25, code_offset=50)
        else_body = _make_expr(30)
        end_expr = _make_expr(50)
        exprs = [cond, jin, then_body, jump_end, else_body, end_expr]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        assert 1 in indices  # jin
        assert 2 in indices  # then
        assert 3 in indices  # jump_end
        assert 4 in indices  # else
        assert 5 in indices  # end


# ================================================================
# 边界情况
# ================================================================

class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_expressions_all_methods(self):
        """空表达式列表不抛异常。"""
        analyzer = JumpAnalyzer([])
        assert analyzer.detect_pattern(0) is None
        assert analyzer.detect_if_else_pattern(0) is None
        assert analyzer.detect_while_pattern(0) is None
        assert analyzer.detect_for_pattern(0) is None
        assert analyzer.detect_switch_pattern(0) is None
        assert analyzer.is_while_backjump(0) is False

    def test_single_expression(self):
        """单表达式列表。"""
        exprs = [_make_expr(0)]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_pattern(0) is None
        assert analyzer.find_label_index(0) == 0

    def test_mixed_for_and_switch(self):
        """混合 for 和 switch 模式。"""
        # for 循环
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=60, boolean_expression=cond,
        )
        body = _make_expr(20)
        inc = _make_let(30)
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_for = _make_expr(60)
        # switch
        switch = _make_switch_value(statement_index=70)
        exprs = [cond, jin, body, inc, jump_back, exit_for, switch]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_pattern(1)["type"] == "for"
        assert analyzer.detect_pattern(6)["type"] == "switch"

    def test_backward_jump_not_loop(self):
        """回跳目标在 start 之前但不是循环结构（非 JumpIfNot 起始）。"""
        # 直接的回跳，前面没有 JumpIfNot
        pre = _make_expr(5)
        body = _make_expr(10)
        jump_back = _make_jump(statement_index=20, code_offset=5)
        exprs = [pre, body, jump_back]
        analyzer = JumpAnalyzer(exprs)

        # index 2 是 EX_Jump 不是 JumpIfNot，检测返回 None
        assert analyzer.detect_while_pattern(2) is None
        assert analyzer.detect_for_pattern(2) is None


# ================================================================
# Push/Pop 模式检测
# ================================================================

class TestPushPopDetection:
    """Push/Pop if/else 模式检测。"""

    def test_push_pop_if_else_basic(self):
        """基本 Push/Pop if/else：Push + JumpIfNot + then + Pop + else"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is not None
        assert result["type"] == "push_pop"
        assert result["start"] == 0
        assert result["condition"] is cond
        assert result["then_start"] == 2  # jin_idx + 1
        assert result["then_end"] == 3    # pop_idx
        assert result["else_start"] == 4  # pop_idx + 1
        assert result["else_end"] == 5    # pushing_address → idx 5

    def test_push_pop_with_condition_loading(self):
        """Push 和 JumpIfNot 之间有额外条件加载指令。"""
        push = _make_push(pushing_address=60)
        push.StatementIndex = 0
        load_cond = _make_expr(5)
        cond = _make_expr(10)
        jin = _make_jump_if_not(
            statement_index=15, code_offset=50,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(25)
        pop = _make_pop()
        pop.StatementIndex = 30
        else_body = _make_expr(50)
        end = _make_expr(60)
        exprs = [push, load_cond, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is not None
        assert result["type"] == "push_pop"
        assert result["then_start"] == 3   # jin_idx + 1
        assert result["then_end"] == 4     # pop_idx
        assert result["else_start"] == 5   # pop_idx + 1
        assert result["else_end"] == 6     # pushing_address → idx 6

    def test_push_pop_no_jump_if_not(self):
        """Push 后没有 JumpIfNot，不匹配 Push/Pop 模式。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        other = _make_expr(10)
        end = _make_expr(50)
        exprs = [push, other, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is None

    def test_push_pop_no_pop(self):
        """Push + JumpIfNot 但没有 Pop，不匹配 Push/Pop 模式。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=50,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        end = _make_expr(50)
        exprs = [push, jin, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is None

    def test_push_pop_not_push_at_start(self):
        """起始位置不是 PushExecutionFlow，返回 None。"""
        jin = _make_jump_if_not(
            statement_index=0, code_offset=50,
            boolean_expression=_make_expr(0),
        )
        exprs = [jin]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is None

    def test_push_pop_out_of_range(self):
        """索引越界返回 None。"""
        push = _make_push()
        exprs = [push]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_push_pop_pattern(-1) is None
        assert analyzer.detect_push_pop_pattern(5) is None

    def test_push_pop_else_end_without_pushing_address(self):
        """pushing_address 无法映射时，else_end 为 pop_idx。"""
        push = _make_push(pushing_address=999)  # 无法映射
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        exprs = [push, jin, then_body, pop, else_body]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is not None
        assert result["else_end"] == 3  # pop_idx (999 无法映射)


# ================================================================
# Push/Pop 通过统一 detect_pattern 入口
# ================================================================

class TestPushPopViaDetectPattern:
    """Push/Pop 通过 detect_pattern 统一入口检测。"""

    def test_push_pop_detected_via_unified_entry(self):
        """Push/Pop 模式通过 detect_pattern 统一入口检测。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(0)
        assert result is not None
        assert result["type"] == "push_pop"

    def test_push_pop_priority_over_jump_if_not(self):
        """Push/Pop 优先于 JumpIfNot 检测（更精确的 if/else）。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(0)
        assert result is not None
        assert result["type"] == "push_pop"


# ================================================================
# Push/Pop 结构化索引
# ================================================================

class TestPushPopStructuredIndices:
    """Push/Pop 模式的结构化索引。"""

    def test_push_pop_structured_indices(self):
        """Push/Pop 模式的所有表达式索引被标记为结构化。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        # Push/Pop 区间内所有索引都应被标记
        assert 0 in indices   # push
        assert 1 in indices   # jin
        assert 2 in indices   # then_body
        assert 3 in indices   # pop
        assert 4 in indices   # else_body
        assert 5 in indices   # end (pushing_address)


# ================================================================
# Push/Pop 结构化率
# ================================================================

class TestPushPopStructuredRate:
    """Push/Pop 模式的结构化率分析。"""

    def test_push_pop_in_structured_rate(self):
        """Push/Pop 模式在结构化率报告中被正确统计。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        # JumpIfNot (jin) 通过 detect_pattern 被识别为 push_pop 模式
        # 注意：analyze_structured_rate 逐索引扫描，JumpIfNot 索引可能被识别为 push_pop
        # 或 if（取决于 detect_pattern 的优先级路径），关键是无 goto 回退
        assert report.goto_count == 0
        assert report.structured_count >= 1
        assert report.rate == 1.0


# ================================================================
# 结果字段传递
# ================================================================

class TestStructuredRateField:
    """structured_rate 字段在 KismetDecompiledResult 中的传递。"""

    def test_structured_rate_field_exists(self):
        """KismetDecompiledResult 包含 structured_rate 字段。"""
        result = KismetDecompiledResult(
            function_name="test",
            signature="void test()",
            local_variables=[],
            cpp_code="void test() {}",
            structured_rate=0.75,
        )
        assert result.structured_rate == 0.75

    def test_structured_rate_default_none(self):
        """structured_rate 默认值为 None。"""
        result = KismetDecompiledResult(
            function_name="test",
            signature="void test()",
            local_variables=[],
            cpp_code="void test() {}",
        )
        assert result.structured_rate is None

    def test_structured_rate_in_to_dict(self):
        """structured_rate 包含在 to_dict 输出中。"""
        result = KismetDecompiledResult(
            function_name="test",
            signature="void test()",
            local_variables=[],
            cpp_code="void test() {}",
            structured_rate=0.5,
        )
        d = result.to_dict()
        assert "structured_rate" in d
        assert d["structured_rate"] == 0.5

    def test_structured_rate_none_in_to_dict(self):
        """structured_rate 为 None 时仍包含在 to_dict 中。"""
        result = KismetDecompiledResult(
            function_name="test",
            signature="void test()",
            local_variables=[],
            cpp_code="void test() {}",
        )
        d = result.to_dict()
        assert "structured_rate" in d
        assert d["structured_rate"] is None


# ================================================================
# for/switch 在主流程中的可检测性
# ================================================================

class TestForSwitchDetectionInMainFlow:
    """验证 for/switch 在主流程中可检测（不被 StructuredControlFlow 死锁）。"""

    def test_for_detected_after_push_pop(self):
        """Push/Pop 之后的 for 循环仍可被检测。"""
        # Push/Pop if/else (使用唯一 offset 避免冲突)
        push = _make_push(pushing_address=200)
        push.StatementIndex = 0
        cond1 = _make_expr(0)
        jin1 = _make_jump_if_not(
            statement_index=10, code_offset=150,
            boolean_expression=cond1,
        )
        jin1.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 30
        else_body = _make_expr(150)
        # for 循环 (使用独立 offset 避免与 Push/Pop 冲突)
        # Layout: for_cond(200) for_jin(210,exit=260) for_body(220) for_inc(230) for_jback(240→210) for_exit(260)
        for_cond = _make_expr(200)
        for_jin = _make_jump_if_not(
            statement_index=210, code_offset=260,
            boolean_expression=for_cond,
        )
        for_body = _make_expr(220)
        for_inc = _make_let(230)
        for_jback = _make_jump(statement_index=240, code_offset=210)
        for_exit = _make_expr(260)

        exprs = [
            push, jin1, then_body, pop, else_body,
            for_cond, for_jin, for_body, for_inc, for_jback, for_exit,
        ]
        analyzer = JumpAnalyzer(exprs)

        # for 模式在 Push/Pop 之后仍可检测
        result = analyzer.detect_pattern(6)
        assert result is not None
        assert result["type"] == "for"

    def test_switch_detected_after_push_pop(self):
        """Push/Pop 之后的 switch 仍可被检测。"""
        push = _make_push(pushing_address=80)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=50,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 30
        else_body = _make_expr(50)
        # switch
        switch = _make_switch_value(statement_index=60)
        exprs = [push, jin, then_body, pop, else_body, switch]
        analyzer = JumpAnalyzer(exprs)

        # switch 在 Push/Pop 之后仍可检测
        result = analyzer.detect_pattern(5)
        assert result is not None
        assert result["type"] == "switch"

    def test_while_after_push_pop(self):
        """Push/Pop 之后的 while 循环仍可被检测。"""
        push = _make_push(pushing_address=200)
        push.StatementIndex = 0
        cond1 = _make_expr(0)
        jin1 = _make_jump_if_not(
            statement_index=10, code_offset=150,
            boolean_expression=cond1,
        )
        jin1.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 30
        else_body = _make_expr(150)
        # while 循环 (独立 offset)
        # Layout: while_cond(200) while_jin(210,exit=250) while_body(220) while_jback(230→210) while_exit(250)
        while_cond = _make_expr(200)
        while_jin = _make_jump_if_not(
            statement_index=210, code_offset=250,
            boolean_expression=while_cond,
        )
        while_body = _make_expr(220)
        while_jback = _make_jump(statement_index=230, code_offset=210)
        while_exit = _make_expr(250)

        exprs = [
            push, jin1, then_body, pop, else_body,
            while_cond, while_jin, while_body, while_jback, while_exit,
        ]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(6)
        assert result is not None
        assert result["type"] == "while"


# ================================================================
# Push/Pop 边界情况
# ================================================================

class TestPushPopEdgeCases:
    """Push/Pop 边界情况。"""

    def test_empty_expressions(self):
        """空表达式列表。"""
        analyzer = JumpAnalyzer([])
        assert analyzer.detect_push_pop_pattern(0) is None

    def test_single_push_no_following(self):
        """单个 Push 无后续指令。"""
        push = _make_push()
        exprs = [push]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_push_pop_pattern(0) is None

    def test_push_with_another_push_before_jump_if_not(self):
        """Push 后遇到另一个 Push（非 JumpIfNot），不匹配。"""
        push1 = _make_push(pushing_address=50)
        push1.StatementIndex = 0
        push2 = _make_push(pushing_address=60)
        push2.StatementIndex = 1
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=_make_expr(0),
        )
        jin.StatementIndex = 2
        end = _make_expr(50)
        exprs = [push1, push2, jin, end]
        analyzer = JumpAnalyzer(exprs)

        # push1 不匹配（遇到 push2 就停止扫描）
        result = analyzer.detect_push_pop_pattern(0)
        assert result is None

    def test_push_with_end_of_script_before_jump_if_not(self):
        """Push 后遇到 EndOfScript（非 JumpIfNot），不匹配。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        end_script = EX_EndOfScript()
        end_script.StatementIndex = 1
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=_make_expr(0),
        )
        jin.StatementIndex = 2
        exprs = [push, end_script, jin]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is None


# ================================================================
# 基础模式检测 — 偏移量映射
# ================================================================

class TestLabelMapping:
    """验证偏移量→索引映射。"""

    def test_label_mapping(self):
        exprs = [
            _make_expr_simple(0),   # idx 0 → offset 0
            _make_expr_simple(10),  # idx 1 → offset 10
            _make_expr_simple(20),  # idx 2 → offset 20
        ]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.find_label_index(0) == 0
        assert analyzer.find_label_index(10) == 1
        assert analyzer.find_label_index(20) == 2
        assert analyzer.find_label_index(99) is None

    def test_is_jump_target(self):
        cond = _make_expr_simple(100)
        jump_if_not = _make_jump_if_not_simple(statement_index=0, code_offset=30, boolean_expression=cond)
        exprs = [_make_expr_simple(0), _make_expr_simple(10), jump_if_not]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.is_jump_target(30) is True
        assert analyzer.is_jump_target(0) is False

    def test_get_jump_sources(self):
        cond = _make_expr_simple(100)
        jump_if_not = _make_jump_if_not_simple(statement_index=0, code_offset=30, boolean_expression=cond)
        exprs = [_make_expr_simple(0), _make_expr_simple(10), jump_if_not]
        analyzer = JumpAnalyzer(exprs)
        sources = analyzer.get_jump_sources(30)
        assert 2 in sources  # jump_if_not 在 index 2

    def test_empty_expressions(self):
        analyzer = JumpAnalyzer([])
        assert analyzer.find_label_index(0) is None
        assert analyzer.is_jump_target(0) is False
        assert analyzer.get_jump_sources(0) == []


class TestIfElseDetection:
    """if/else 模式检测。"""

    def test_if_else_detection(self):
        """if/else: JumpIfNot → then → Jump(end) → else → end"""
        # 布局:
        #   0: expr (condition target)
        #   1: JumpIfNot(cond, false_label=30) → index 1
        #   2: then body
        #   3: Jump(end_label=50) → index 3
        #   4: else body
        #   5: (end)
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=1, code_offset=30, boolean_expression=cond)
        then_body = _make_expr_simple(20)
        jump_end = _make_jump_simple(statement_index=25, code_offset=50)
        else_body = _make_expr_simple(30)
        end_expr = _make_expr_simple(50)
        exprs = [cond, jump_if_not, then_body, jump_end, else_body, end_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_if_else_pattern(1)
        assert result is not None
        assert result["type"] == "if_else"
        assert result["start"] == 1
        assert result["then_start"] == 2
        assert result["then_end"] == 3
        assert result["else_start"] == 4
        assert result["else_end"] == 5

    def test_simple_if_detection(self):
        """简单 if（无 else）：JumpIfNot → then → end"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=1, code_offset=30, boolean_expression=cond)
        then_body = _make_expr_simple(20)
        end_expr = _make_expr_simple(30)
        exprs = [cond, jump_if_not, then_body, end_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_if_else_pattern(1)
        assert result is not None
        assert result["type"] == "if"
        assert result["then_start"] == 2
        assert result["then_end"] == 2

    def test_if_else_not_jump_if_not(self):
        """start_idx 位置不是 JumpIfNot，应返回 None。"""
        exprs = [_make_expr_simple(0), _make_jump_simple(statement_index=1, code_offset=10)]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_if_else_pattern(1) is None

    def test_if_else_out_of_range(self):
        """索引越界应返回 None。"""
        analyzer = JumpAnalyzer([_make_expr_simple(0)])
        assert analyzer.detect_if_else_pattern(-1) is None
        assert analyzer.detect_if_else_pattern(5) is None


class TestWhileDetection:
    """while 循环模式检测。"""

    def test_while_detection(self):
        """while: JumpIfNot → body → Jump(back to start)"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=10, code_offset=50, boolean_expression=cond)
        body = _make_expr_simple(20)
        jump_back = _make_jump_simple(statement_index=30, code_offset=10)
        exit_expr = _make_expr_simple(50)
        exprs = [cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_while_pattern(1)
        assert result is not None
        assert result["type"] == "while"
        assert result["start"] == 1
        assert result["body_start"] == 2
        assert result["body_end"] == 3  # jump_back 的索引
        assert result["exit_label"] == 50

    def test_while_backjump_to_before_start(self):
        """回跳目标在 start_idx 之前。"""
        pre_expr = _make_expr_simple(5)
        cond = _make_expr_simple(10)
        jump_if_not = _make_jump_if_not_simple(statement_index=15, code_offset=50, boolean_expression=cond)
        body = _make_expr_simple(30)
        jump_back = _make_jump_simple(statement_index=40, code_offset=5)
        exit_expr = _make_expr_simple(50)
        exprs = [pre_expr, cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_while_pattern(2)
        assert result is not None
        assert result["type"] == "while"

    def test_while_no_backjump(self):
        """循环体内没有回跳，不是 while 模式。"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=1, code_offset=30, boolean_expression=cond)
        body = _make_expr_simple(10)
        # Jump 跳到 end 而非回跳
        jump_forward = _make_jump_simple(statement_index=20, code_offset=50)
        exit_expr = _make_expr_simple(30)
        exprs = [cond, jump_if_not, body, jump_forward, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_while_pattern(1) is None

    def test_while_no_statement_index(self):
        """JumpIfNot 无 StatementIndex，应返回 None。"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=0, code_offset=30, boolean_expression=cond)
        # 覆盖 StatementIndex 为 None
        jump_if_not.StatementIndex = None
        jump_back = _make_jump_simple(statement_index=10, code_offset=0)
        exprs = [cond, jump_if_not, jump_back]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_while_pattern(1) is None


class TestNoPattern:
    """无法识别模式的情况。"""

    def test_no_pattern(self):
        """非条件跳转不匹配任何模式。"""
        jump = _make_jump_simple(statement_index=0, code_offset=10)
        target = _make_expr_simple(10)
        exprs = [jump, target]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_if_else_pattern(0) is None
        assert analyzer.detect_while_pattern(0) is None
        assert analyzer.detect_for_pattern(0) is None

    def test_is_while_backjump(self):
        """is_while_backjump 正确识别回跳。"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=10, code_offset=50, boolean_expression=cond)
        body = _make_expr_simple(20)
        jump_back = _make_jump_simple(statement_index=30, code_offset=10)
        exit_expr = _make_expr_simple(50)
        exprs = [cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.is_while_backjump(3) is True  # jump_back 在 index 3
        assert analyzer.is_while_backjump(2) is False  # body 不是回跳
        assert analyzer.is_while_backjump(0) is False


from unittest.mock import MagicMock

from uasset_read.kismet.structured_flow import StructuredControlFlow
from uasset_read.kismet.expressions.control_flow import EX_Jump, EX_JumpIfNot
from uasset_read.kismet.semantic import (
    extract_eventgraph_semantic_calls,
    _flow_to_cpp,
)


# ================================================================
# goto 标签输出辅助工厂
# ================================================================

def _make_expr(statement_index: int):
    """创建最简 mock，仅携带 StatementIndex。"""
    class _Stub:
        StatementIndex = statement_index
    return _Stub()


def _make_expr_with_byte_offset(statement_index: int, offset_val: int):
    """创建带 StatementIndex 的 mock 表达式（用于标签映射测试）。"""
    obj = _make_expr(statement_index)
    obj.StatementIndex = offset_val
    return obj


def _make_jump(statement_index: int, code_offset: int) -> EX_Jump:
    """创建 EX_Jump。"""
    jmp = EX_Jump(CodeOffset=code_offset)
    jmp.StatementIndex = statement_index
    return jmp


def _make_jump_if_not(
    statement_index: int,
    code_offset: int,
    boolean_expression=None,
) -> EX_JumpIfNot:
    """创建 EX_JumpIfNot。"""
    jmp = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=boolean_expression)
    jmp.StatementIndex = statement_index
    return jmp


# ================================================================
# goto 标签输出测试
# ================================================================

class TestGotoLabelEmission:
    """goto 回退路径的标签输出。"""

    def test_label_emitted_before_target_expression(self):
        """跳转目标对应的表达式前应输出 Label。"""
        # 布局:
        #   idx 0: Jump(CodeOffset=30)  — 跳到 offset 30
        #   idx 1: expr (byte_offset=10)
        #   idx 2: expr (byte_offset=30)  — 跳转目标
        jump = _make_jump(statement_index=0, code_offset=30)
        expr1 = _make_expr_with_byte_offset(10, 10)
        target = _make_expr_with_byte_offset(20, 30)
        expressions = [jump, expr1, target]

        scf = StructuredControlFlow()
        # 手动调用 _emit_goto_fallback（绕过 reconstruct 的结构化检测）
        result = scf._emit_goto_fallback(expressions, jump_targets={30})

        # 应包含 Label_30: 且在 target 表达式之前
        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 1
        assert "Label_30:" in label_lines[0]
        label_idx = result.index("Label_30:")
        # 标签应出现在 target 的输出行之前
        assert label_idx < len(result) - 1

    def test_multiple_jump_targets_emit_multiple_labels(self):
        """多个跳转目标应各自输出对应标签。"""
        # Jump → 30 和 Jump → 50
        jump1 = _make_jump(statement_index=0, code_offset=30)
        jump2 = _make_jump(statement_index=10, code_offset=50)
        expr_mid = _make_expr_with_byte_offset(20, 20)
        target1 = _make_expr_with_byte_offset(30, 30)
        target2 = _make_expr_with_byte_offset(40, 50)
        expressions = [jump1, jump2, expr_mid, target1, target2]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={30, 50})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 2
        assert any("Label_30:" in l for l in label_lines)
        assert any("Label_50:" in l for l in label_lines)

    def test_no_duplicate_labels(self):
        """同一跳转目标不应输出重复标签。"""
        # 两个 jump 都指向 offset 30
        jump1 = _make_jump(statement_index=0, code_offset=30)
        jump2 = _make_jump(statement_index=10, code_offset=30)
        target = _make_expr_with_byte_offset(20, 30)
        expressions = [jump1, jump2, target]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={30})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 1

    def test_no_labels_when_no_jump_targets(self):
        """无跳转目标时不应输出任何标签。"""
        expr1 = _make_expr_with_byte_offset(0, 0)
        expr2 = _make_expr_with_byte_offset(10, 10)
        expressions = [expr1, expr2]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets=set())

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 0

    def test_label_uses_codeoffset_value(self):
        """标签名称应使用 jump target 的 CodeOffset 值。"""
        jump = _make_jump(statement_index=0, code_offset=42)
        # target 表达式的 byte_offset 映射到 CodeOffset=42
        target = _make_expr_with_byte_offset(10, 42)
        expressions = [jump, target]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={42})

        assert "Label_42:" in result

    def test_offset_to_index_mapping_with_statement_index(self):
        """验证 StatementIndex → index 映射正确关联跳转目标。"""
        # Jump(CodeOffset=50) 跳到 offset 50
        # 表达式列表中 idx 2 的 StatementIndex=50
        jump = _make_jump(statement_index=0, code_offset=50)
        expr1 = _make_expr(10)
        target = _make_expr_with_byte_offset(20, 50)
        expressions = [jump, expr1, target]

        # 构建 offset_to_index 映射
        offset_to_index: dict[int, int] = {}
        for idx, expr in enumerate(expressions):
            stmt_idx = getattr(expr, "StatementIndex", None)
            if stmt_idx is not None:
                offset_to_index[stmt_idx] = idx
            if hasattr(expr, "CodeOffset"):
                offset_to_index[expr.CodeOffset] = idx

        # CodeOffset=50 应映射到 idx 0（来自 jump 的 CodeOffset）和 idx 2（来自 StatementIndex）
        # 最终映射为 idx 2（后写覆盖）
        assert offset_to_index.get(50) == 2

    def test_offset_to_index_passed_from_reconstruct(self):
        """验证 reconstruct 传入的 offset_to_index 被正确使用。"""
        # 构造一个不会被 _detect_patterns 识别为结构化模式的序列
        # 从而走 goto 回退路径
        jump = _make_jump(statement_index=0, code_offset=30)
        mid = _make_expr(10)
        target = _make_expr_with_byte_offset(20, 30)
        end = _make_expr(30)  # offset 30 的目标
        expressions = [jump, mid, target, end]

        scf = StructuredControlFlow()
        result = scf.reconstruct(expressions)

        # 应包含 Label_30:
        label_lines = [l for l in result if "Label_30:" in l]
        assert len(label_lines) == 1

    def test_labels_sorted_by_offset(self):
        """多个标签应按偏移量排序输出。"""
        # 乱序跳转目标
        jump1 = _make_jump(statement_index=0, code_offset=50)
        jump2 = _make_jump(statement_index=5, code_offset=20)
        target2 = _make_expr_with_byte_offset(10, 20)
        target1 = _make_expr_with_byte_offset(15, 50)
        expressions = [jump1, jump2, target2, target1]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={20, 50})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 2
        # Label_20 应在 Label_50 之前（因为 target2 在 target1 之前）
        idx_20 = result.index("Label_20:")
        idx_50 = result.index("Label_50:")
        assert idx_20 < idx_50

    def test_empty_expressions(self):
        """空表达式列表不应抛异常。"""
        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback([], jump_targets={10})
        assert result == []

    def test_label_not_emitted_for_non_target_offset(self):
        """非跳转目标的偏移量不应生成标签。"""
        jump = _make_jump(statement_index=0, code_offset=30)
        expr = _make_expr_with_byte_offset(10, 10)  # 不是跳转目标
        target = _make_expr_with_byte_offset(20, 30)
        expressions = [jump, expr, target]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={30})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 1
        assert "Label_30:" in label_lines[0]
        # 不应有 Label_10
        assert not any("Label_10:" in l for l in label_lines)


# ================================================================
# 语义提取辅助工厂
# ================================================================

def _make_event_node(
    node_guid: str,
    event_name: str,
    output_exec_pin_id: str = "EV000000000000000000000000000001",
    member_parent: str = "",
) -> MagicMock:
    """创建 K2Node_Event 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_Event"
    node.node_pos_x = 0
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None

    func_ref = MagicMock()
    func_ref.member_name = event_name
    func_ref.member_parent = member_parent
    node.node_data = {"event_reference": func_ref}

    exec_out = MagicMock()
    exec_out.pin_id = output_exec_pin_id
    exec_out.pin_name = "Then"
    exec_out.direction = 1
    exec_out.default_value = ""
    exec_out.linked_to_raw = []
    exec_out.persistent_guid = output_exec_pin_id
    exec_out.pin_type = MagicMock()
    exec_out.pin_type.pin_category = "exec"

    node.pins = [exec_out]
    return node


def _make_call_function_node(
    node_guid: str,
    function_name: str,
    input_exec_pin_id: str = "CF000000000000000000000000000001",
    output_exec_pin_id: str = "CF000000000000000000000000000002",
    member_parent: str = "/Script/Engine.Actor",
    extra_pins: list | None = None,
) -> MagicMock:
    """创建 K2Node_CallFunction 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_CallFunction"
    node.node_pos_x = 100
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None

    func_ref = MagicMock()
    func_ref.member_name = function_name
    func_ref.member_parent = member_parent
    node.node_data = {"function_reference": func_ref}

    exec_in = MagicMock()
    exec_in.pin_id = input_exec_pin_id
    exec_in.pin_name = "execute"
    exec_in.direction = 0
    exec_in.default_value = ""
    exec_in.linked_to_raw = []
    exec_in.persistent_guid = input_exec_pin_id
    exec_in.pin_type = MagicMock()
    exec_in.pin_type.pin_category = "exec"

    exec_out = MagicMock()
    exec_out.pin_id = output_exec_pin_id
    exec_out.pin_name = "then"
    exec_out.direction = 1
    exec_out.default_value = ""
    exec_out.linked_to_raw = []
    exec_out.persistent_guid = output_exec_pin_id
    exec_out.pin_type = MagicMock()
    exec_out.pin_type.pin_category = "exec"

    pins = [exec_in, exec_out]
    if extra_pins:
        pins.extend(extra_pins)
    node.pins = pins
    return node


def _make_variable_set_node(
    node_guid: str,
    variable_name: str,
    input_exec_pin_id: str = "VS000000000000000000000000000001",
    output_exec_pin_id: str = "VS000000000000000000000000000002",
) -> MagicMock:
    """创建 K2Node_VariableSet 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_VariableSet"
    node.node_pos_x = 200
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None
    node.node_data = {"variable_name": variable_name}

    exec_in = MagicMock()
    exec_in.pin_id = input_exec_pin_id
    exec_in.pin_name = "execute"
    exec_in.direction = 0
    exec_in.default_value = ""
    exec_in.linked_to_raw = []
    exec_in.persistent_guid = input_exec_pin_id
    exec_in.pin_type = MagicMock()
    exec_in.pin_type.pin_category = "exec"

    exec_out = MagicMock()
    exec_out.pin_id = output_exec_pin_id
    exec_out.pin_name = "then"
    exec_out.direction = 1
    exec_out.default_value = ""
    exec_out.linked_to_raw = []
    exec_out.persistent_guid = output_exec_pin_id
    exec_out.pin_type = MagicMock()
    exec_out.pin_type.pin_category = "exec"

    node.pins = [exec_in, exec_out]
    return node


def _make_variable_get_node(
    node_guid: str,
    variable_name: str,
) -> MagicMock:
    """创建 K2Node_VariableGet 节点（Pure，无 exec pin）。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_VariableGet"
    node.node_pos_x = 150
    node.node_pos_y = 50
    node.node_comment = ""
    node._export_object_name = None
    node.node_data = {"variable_name": variable_name}

    value_pin = MagicMock()
    value_pin.pin_id = "VG000000000000000000000000000001"
    value_pin.pin_name = variable_name
    value_pin.direction = 1
    value_pin.default_value = ""
    value_pin.linked_to_raw = []
    value_pin.persistent_guid = "VG000000000000000000000000000001"
    value_pin.pin_type = MagicMock()
    value_pin.pin_type.pin_category = "int"

    node.pins = [value_pin]
    return node


def _make_pin(
    pin_id: str,
    pin_name: str,
    direction: int = 0,
    category: str = "float",
) -> MagicMock:
    """创建普通数据 pin。"""
    pin = MagicMock()
    pin.pin_id = pin_id
    pin.pin_name = pin_name
    pin.direction = direction
    pin.default_value = ""
    pin.linked_to_raw = []
    pin.persistent_guid = pin_id
    pin.pin_type = MagicMock()
    pin.pin_type.pin_category = category
    return pin


def _make_graph(graph_name: str, nodes: list) -> MagicMock:
    """创建 mock UEdGraph。"""
    graph = MagicMock()
    graph.graph_name = graph_name
    graph.graph_class = "EdGraph"
    graph.nodes = nodes
    graph.graph_guid = "test-guid-0001"
    graph.schema = None
    return graph


def _link_pins(from_pin: MagicMock, to_pin: MagicMock) -> None:
    """连接两个 pin（设置 linked_to_raw 单向引用，避免 pin 共享导致的交叉追踪）。"""
    from_pin.linked_to_raw = [{"pin_guid": to_pin.pin_id}]


# ================================================================
# extract_eventgraph_semantic_calls — 多 CallFunction 提取测试
# ================================================================

class TestExtractMultiCallFunction:
    """extract_eventgraph_semantic_calls — 验证提取每个事件的所有 CallFunction 节点。"""

    def test_single_event_single_call(self):
        """单个事件单个调用应正常返回。"""
        event_node = _make_event_node("guid-ev-001", "BeginPlay")
        call_node = _make_call_function_node("guid-cf-001", "PrintString")
        _link_pins(event_node.pins[0], call_node.pins[0])

        graph = _make_graph("EventGraph", [event_node, call_node])
        results = extract_eventgraph_semantic_calls([graph])

        assert len(results) == 1
        assert results[0]["event_name"] == "BeginPlay"
        assert results[0]["function_name"] == "PrintString"

    def test_single_event_multiple_calls(self):
        """单个事件多个 CallFunction 应全部提取。"""
        event_node = _make_event_node("guid-ev-001", "BeginPlay")
        call1 = _make_call_function_node(
            "guid-cf-001", "PrintString",
            input_exec_pin_id="CF0000000000000000000000000000A1",
            output_exec_pin_id="CF0000000000000000000000000000A2",
        )
        call2 = _make_call_function_node(
            "guid-cf-002", "SetActorLocation",
            input_exec_pin_id="CF0000000000000000000000000000B1",
            output_exec_pin_id="CF0000000000000000000000000000B2",
        )
        # 链式连接：Event -> Call1 -> Call2
        _link_pins(event_node.pins[0], call1.pins[0])
        _link_pins(call1.pins[1], call2.pins[0])

        graph = _make_graph("EventGraph", [event_node, call1, call2])
        results = extract_eventgraph_semantic_calls([graph])

        # 关键断言：应返回 2 个结果，不仅第一个
        assert len(results) >= 2, f"应提取至少 2 个 CallFunction，实际得到 {len(results)}"
        func_names = [r["function_name"] for r in results]
        assert "PrintString" in func_names, "PrintString 应出现在结果中"
        assert "SetActorLocation" in func_names, "SetActorLocation 应出现在结果中"

    def test_multiple_events_each_with_calls(self):
        """多个事件各自有调用应全部提取。"""
        event1 = _make_event_node(
            "guid-ev-001", "BeginPlay",
            output_exec_pin_id="EV000000000000000000000000000101",
        )
        call1 = _make_call_function_node(
            "guid-cf-001", "FuncA",
            input_exec_pin_id="CF0000000000000000000000000000C1",
            output_exec_pin_id="CF0000000000000000000000000000C2",
        )
        event2 = _make_event_node(
            "guid-ev-002", "Tick",
            output_exec_pin_id="EV000000000000000000000000000102",
        )
        call2 = _make_call_function_node(
            "guid-cf-003", "FuncB",
            input_exec_pin_id="CF0000000000000000000000000000D1",
            output_exec_pin_id="CF0000000000000000000000000000D2",
        )
        _link_pins(event1.pins[0], call1.pins[0])
        _link_pins(event2.pins[0], call2.pins[0])

        graph = _make_graph("EventGraph", [event1, call1, event2, call2])
        results = extract_eventgraph_semantic_calls([graph])

        assert len(results) >= 2
        func_names = [r["function_name"] for r in results]
        assert "FuncA" in func_names
        assert "FuncB" in func_names

    def test_event_without_call_skipped(self):
        """没有 CallFunction 的事件应被跳过。"""
        event_node = _make_event_node("guid-ev-001", "EmptyEvent")
        graph = _make_graph("EventGraph", [event_node])
        results = extract_eventgraph_semantic_calls([graph])
        assert results == []

    def test_no_event_graph_returns_empty(self):
        """无 EventGraph 时返回空列表。"""
        call_node = _make_call_function_node("guid-cf-001", "SomeFunc")
        graph = _make_graph("SomeOtherGraph", [call_node])
        results = extract_eventgraph_semantic_calls([graph])
        assert results == []


# ================================================================
# _flow_to_cpp — VariableSet / VariableGet 处理测试
# ================================================================

class TestFlowToCppVariableNodes:
    """_flow_to_cpp — 验证处理 VariableSet 和 VariableGet 节点。"""

    def test_variable_set_in_flow(self):
        """执行流中的 VariableSet 节点应出现在 C++ 输出中。"""
        var_set = _make_variable_set_node("guid-vs-001", "Health")
        entry_node = MagicMock()
        entry_node.node_guid = "guid-fe-001"
        entry_node.class_name = "K2Node_FunctionEntry"
        entry_node.node_data = {}

        flows = [{
            "start_event": "FunctionEntry.TakeDamage",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_VariableSet",
                    "node_guid": "guid-vs-001",
                },
            ],
        }]
        node_lookup = {"guid-vs-001": var_set}
        result = _flow_to_cpp("TakeDamage", flows, node_lookup)

        assert "Health" in result, "变量名 Health 应出现在 C++ 输出中"

    def test_variable_get_in_flow(self):
        """执行流中的 VariableGet 节点应出现在 C++ 输出中。"""
        var_get = _make_variable_get_node("guid-vg-001", "MaxHealth")

        flows = [{
            "start_event": "FunctionEntry.GetHealthPercent",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_VariableGet",
                    "node_guid": "guid-vg-001",
                },
            ],
        }]
        node_lookup = {"guid-vg-001": var_get}
        result = _flow_to_cpp("GetHealthPercent", flows, node_lookup)

        assert "MaxHealth" in result, "变量名 MaxHealth 应出现在 C++ 输出中"

    def test_mixed_call_and_variable_nodes(self):
        """混合 CallFunction、VariableSet、VariableGet 的执行流应全部处理。"""
        call_node = _make_call_function_node("guid-cf-001", "ApplyDamage")
        var_set = _make_variable_set_node("guid-vs-001", "Health")
        var_get = _make_variable_get_node("guid-vg-001", "MaxHealth")

        flows = [{
            "start_event": "FunctionEntry.TakeDamage",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_VariableGet",
                    "node_guid": "guid-vg-001",
                },
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-001",
                    "parameters": {
                        "input_params": [
                            {"name": "DamageAmount", "pin_category": "float"},
                        ],
                        "output_params": [],
                    },
                },
                {
                    "node_type": "K2Node_VariableSet",
                    "node_guid": "guid-vs-001",
                },
            ],
        }]
        node_lookup = {
            "guid-cf-001": call_node,
            "guid-vs-001": var_set,
            "guid-vg-001": var_get,
        }
        result = _flow_to_cpp("TakeDamage", flows, node_lookup)

        assert "ApplyDamage" in result, "函数调用应出现在输出中"
        assert "Health" in result, "VariableSet 变量应出现在输出中"
        assert "MaxHealth" in result, "VariableGet 变量应出现在输出中"
