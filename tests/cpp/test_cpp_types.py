"""C++ 类型与格式化测试 — 合并自 test_cpp_class_scope.py、test_cpp_default_value.py 和 test_cpp_wrapper_nesting.py。

覆盖：类作用域 ClassName:: 前缀、默认值空输出修复、函数体包裹剥离。
"""
from __future__ import annotations

import pytest

from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppCallParameter,
    CppClassIR,
    CppHeaderMeta,
    CppMethodIR,
    CppCallStmt,
    CppAssignmentStmt,
)
from uasset_read.cpp_gen.formatters.cpp_function_body_formatter import (
    format_cpp_function_body,
    format_full_cpp_implementation,
)
from uasset_read.cpp_gen.formatters.cpp_header_formatter import (
    format_cpp_header,
)


# ============================================================================
# 辅助工厂函数
# ============================================================================

def _make_method(
    cpp_name: str,
    return_type: str = "void",
    class_name: str = "UMyClass",
    is_static: bool = False,
    body_text: str = None,
    parameters=None,
) -> CppMethodIR:
    """创建测试用 CppMethodIR。"""
    if parameters is None:
        parameters = []
    return CppMethodIR(
        cpp_name=cpp_name,
        return_type=return_type,
        parameters=parameters or [],
        ufunction_specifiers=["BlueprintCallable"],
        is_override=False,
        is_static=is_static,
        class_name=class_name,
        body_text=body_text,
    )


def _make_class_ir(class_name: str = "UMyClass", methods=None) -> CppClassIR:
    """创建测试用 CppClassIR。"""
    return CppClassIR(
        name=class_name,
        parent_class="UObject",
        header_meta=CppHeaderMeta.build_from_parent("UObject", class_name),
        properties=[],
        methods=methods or [],
    )


# ============================================================================
# .cpp 实现中的 ClassName:: 前缀测试
# ============================================================================

class TestCppClassScopeImplementation:
    """测试 .cpp 实现文件中方法签名包含 ClassName:: 前缀。"""

    def test_method_has_class_prefix(self):
        """普通方法实现必须有 ClassName:: 前缀。"""
        method = _make_method("MyFunction", body_text="    DoSomething();")
        result = format_cpp_function_body(method)
        assert "UMyClass::MyFunction" in result
        # 确保没有裸方法名（不含 ClassName:: 的签名行）
        sig_line = result.split("\n")[0]
        assert "UMyClass::" in sig_line

    def test_static_method_has_class_prefix(self):
        """静态方法实现必须有 ClassName:: 前缀。"""
        method = _make_method(
            "GetDefault",
            return_type="UMyClass*",
            is_static=True,
            body_text="    return nullptr;",
        )
        result = format_cpp_function_body(method)
        assert "UMyClass::GetDefault" in result

    def test_constructor_has_class_prefix(self):
        """构造函数实现必须有 ClassName:: 前缀。"""
        method = _make_method(
            "UMyClass",
            return_type="",
            body_text="",
        )
        result = format_cpp_function_body(method)
        assert "UMyClass::UMyClass" in result

    def test_destructor_has_class_prefix(self):
        """析构函数实现必须有 ClassName:: 前缀。"""
        method = _make_method(
            "~UMyClass",
            return_type="",
            body_text="",
        )
        result = format_cpp_function_body(method)
        assert "UMyClass::~UMyClass" in result

    def test_method_with_parameters_has_class_prefix(self):
        """带参数的方法实现必须有 ClassName:: 前缀。"""
        params = [
            CppCallParameter(name="Speed", cpp_type="float", direction="input"),
            CppCallParameter(name="Direction", cpp_type="FVector", direction="input"),
        ]
        method = _make_method(
            "MoveTo",
            return_type="bool",
            parameters=params,
            body_text="    return true;",
        )
        result = format_cpp_function_body(method)
        assert "UMyClass::MoveTo(float Speed, FVector Direction)" in result

    def test_method_without_class_name_no_prefix(self):
        """没有 class_name 的方法不添加前缀（兼容模式）。"""
        method = CppMethodIR(
            cpp_name="OrphanMethod",
            return_type="void",
            parameters=[],
            ufunction_specifiers=[],
            is_override=False,
            class_name="",
            body_text="    // standalone;",
        )
        result = format_cpp_function_body(method)
        sig_line = result.split("\n")[0]
        assert "::" not in sig_line
        assert "void OrphanMethod()" in sig_line

    def test_full_implementation_sets_class_prefix(self):
        """format_full_cpp_implementation 为所有方法添加 ClassName:: 前缀。"""
        methods = [
            _make_method("FuncA", class_name="", body_text="    A();"),
            _make_method("FuncB", class_name="", body_text="    B();"),
        ]
        ir = _make_class_ir("ABP_MyActor", methods=methods)
        result = format_full_cpp_implementation(ir)
        assert "ABP_MyActor::FuncA" in result
        assert "ABP_MyActor::FuncB" in result

    def test_full_implementation_propagates_class_name(self):
        """format_full_cpp_implementation 将 ir.name 传播到没有 class_name 的方法。"""
        method = CppMethodIR(
            cpp_name="Standalone",
            return_type="void",
            parameters=[],
            ufunction_specifiers=[],
            is_override=False,
            class_name="",
            body_text="    // test;",
        )
        ir = _make_class_ir("UMyComponent", methods=[method])
        result = format_full_cpp_implementation(ir)
        assert "UMyComponent::Standalone" in result
        # 验证 method 对象的 class_name 已被设置
        assert method.class_name == "UMyComponent"

    def test_full_implementation_preserves_existing_class_name(self):
        """format_full_cpp_implementation 不覆盖已有的 class_name。"""
        method = _make_method("Existing", class_name="UOtherClass", body_text="    // test;")
        ir = _make_class_ir("UMyClass", methods=[method])
        result = format_full_cpp_implementation(ir)
        # 已有的 class_name 不应被覆盖
        assert "UOtherClass::Existing" in result

    def test_constructor_in_implementation_output(self):
        """构造函数在 format_full_cpp_implementation 输出中使用 ClassName:: 前缀。"""
        # 构造函数通过 format_cpp_constructor 生成，不通过 format_full_cpp_implementation
        # 但单独调用 format_cpp_function_body 时应有前缀
        method = _make_method("ABP_MyActor", return_type="", class_name="ABP_MyActor", body_text="")
        result = format_cpp_function_body(method)
        assert "ABP_MyActor::ABP_MyActor" in result


# ============================================================================
# .h 头文件声明中不应有 ClassName:: 前缀
# ============================================================================

class TestCppHeaderNoClassScope:
    """测试 .h 头文件声明中方法名不包含 ClassName:: 前缀。"""

    def test_header_declaration_no_class_prefix(self):
        """头文件中的方法声明不应有 ClassName:: 前缀。"""
        method = _make_method("MyFunction", body_text="    // not used in header")
        ir = _make_class_ir("UMyClass", methods=[method])
        result = format_cpp_header(ir)
        # 头文件中不应出现 ClassName::MethodName 形式
        assert "UMyClass::MyFunction" not in result
        # 但应有裸方法名
        assert "MyFunction" in result

    def test_header_static_declaration_no_class_prefix(self):
        """头文件中的静态方法声明不应有 ClassName:: 前缀。"""
        method = _make_method("GetDefault", return_type="UMyClass*", is_static=True)
        ir = _make_class_ir("UMyClass", methods=[method])
        result = format_cpp_header(ir)
        assert "UMyClass::GetDefault" not in result
        assert "GetDefault" in result

    def test_header_constructor_no_class_prefix_in_signature(self):
        """头文件中构造函数声明在类内部，不需要 ClassName:: 前缀。"""
        ir = _make_class_ir("ABP_MyActor")
        result = format_cpp_header(ir)
        # 头文件中的构造函数声明：ABP_MyActor();
        # 不应出现 ABP_MyActor::ABP_MyActor()
        assert "ABP_MyActor::ABP_MyActor" not in result
        assert "ABP_MyActor();" in result

    def test_header_multiple_methods_no_prefix(self):
        """头文件中多个方法声明都不应有 ClassName:: 前缀。"""
        methods = [
            _make_method("FuncA"),
            _make_method("FuncB"),
            _make_method("FuncC", is_static=True),
        ]
        ir = _make_class_ir("UMyClass", methods=methods)
        result = format_cpp_header(ir)
        # 不应有任何 ClassName:: 前缀（除 class 声明行本身）
        for line in result.split("\n"):
            # 跳过 class 声明行和构造函数声明
            if "class " in line or line.strip().startswith("//"):
                continue
            # 在方法声明行中不应有 ::
            stripped = line.strip()
            if stripped.startswith("void") or stripped.startswith("static"):
                assert "::" not in stripped, f"头文件声明不应有 ClassName:: 前缀: {stripped}"


# ============================================================================
# 边界情况
# ============================================================================

class TestEdgeCases:
    """测试边界情况。"""

    def test_empty_class_name_fallback(self):
        """class_name 为空时不添加前缀。"""
        method = CppMethodIR(
            cpp_name="Test",
            return_type="void",
            parameters=[],
            ufunction_specifiers=[],
            is_override=False,
            class_name="",
            body_text="    // test;",
        )
        result = format_cpp_function_body(method)
        sig_line = result.split("\n")[0]
        assert sig_line == "void Test()"

    def test_class_name_with_special_chars(self):
        """类名含下划线时前缀正确。"""
        method = _make_method("Init", class_name="ABP_FirstPersonCharacter_C", body_text="    // init;")
        result = format_cpp_function_body(method)
        assert "ABP_FirstPersonCharacter_C::Init" in result

    def test_struct_class_prefix(self):
        """F 前缀结构体的类作用域正确。"""
        method = _make_method("Serialize", class_name="FMyStruct", body_text="    // serialize;")
        result = format_cpp_function_body(method)
        assert "FMyStruct::Serialize" in result


# ==============================================================================
# 以下来自 test_cpp_default_value.py
# ==============================================================================

"""C++ 默认值空输出修复测试。

验证：
- 空值不输出 "= ;"
- 有值正常输出 "= value"
- format_cpp_default_value 和 _format_default_value 均正确处理空值
"""

import unittest
from typing import List

from uasset_read.cpp_gen.cpp_default_value_formatter import format_cpp_default_value
from uasset_read.cpp_gen.formatters.cpp_header_formatter import (
    _format_default_value,
    _format_variable_property,
)
from uasset_read.cpp_gen.formatters.cpp_json_ir import CppProperty


def _make_variable_property(
    name: str,
    cpp_type: str,
    default_value=None,
    marks: List[str] | None = None,
) -> CppProperty:
    """构建变量 CppProperty 测试对象。"""
    if marks is None:
        marks = ["EditAnywhere", "BlueprintReadWrite"]
    return CppProperty(
        cpp_type=cpp_type,
        name=name,
        uproperty_marks=marks,
        category="variable",
        default_value=default_value,
    )


class TestFormatCppDefaultValueEmpty(unittest.TestCase):
    """测试 format_cpp_default_value 空值处理。"""

    def test_none_returns_empty(self) -> None:
        """None 值应返回空字符串。"""
        self.assertEqual(format_cpp_default_value(None, "float"), "")

    def test_empty_string_returns_empty(self) -> None:
        """空字符串应返回空字符串，不产生输出。"""
        self.assertEqual(format_cpp_default_value("", "FString"), "")
        self.assertEqual(format_cpp_default_value("", "float"), "")
        self.assertEqual(format_cpp_default_value("", "int32"), "")

    def test_whitespace_string_returns_empty(self) -> None:
        """纯空白字符串应返回空字符串。"""
        self.assertEqual(format_cpp_default_value("  ", "FString"), "")
        self.assertEqual(format_cpp_default_value("\t", "FString"), "")
        self.assertEqual(format_cpp_default_value("\n", "FString"), "")

    def test_valid_float_value(self) -> None:
        """有效 float 值应正常格式化。"""
        self.assertEqual(format_cpp_default_value(100.0, "float"), "100.f")
        self.assertEqual(format_cpp_default_value(3.14, "float"), "3.14f")

    def test_valid_bool_value(self) -> None:
        """有效 bool 值应正常格式化。"""
        self.assertEqual(format_cpp_default_value(True, "bool"), "true")
        self.assertEqual(format_cpp_default_value(False, "bool"), "false")

    def test_valid_int_value(self) -> None:
        """有效 int 值应正常格式化。"""
        self.assertEqual(format_cpp_default_value(42, "int32"), "42")

    def test_valid_string_value(self) -> None:
        """有效字符串值应正常格式化。"""
        self.assertEqual(
            format_cpp_default_value("hello", "FString"),
            'TEXT("hello")',
        )

    def test_valid_enum_value(self) -> None:
        """有效枚举值应正常格式化。"""
        self.assertEqual(
            format_cpp_default_value("FirstPerson", "EFirstPersonPrimitiveType"),
            "FirstPerson",
        )


class TestFormatDefaultValueEmpty(unittest.TestCase):
    """测试 cpp_header_formatter._format_default_value 空值处理。"""

    def test_none_returns_empty(self) -> None:
        self.assertEqual(_format_default_value("float", None), "")

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(_format_default_value("FString", ""), "")

    def test_whitespace_string_returns_empty(self) -> None:
        self.assertEqual(_format_default_value("FString", "   "), "")

    def test_valid_float(self) -> None:
        self.assertEqual(_format_default_value("float", 100.0), "100.0f")

    def test_valid_bool(self) -> None:
        self.assertEqual(_format_default_value("bool", True), "true")

    def test_valid_int(self) -> None:
        self.assertEqual(_format_default_value("int32", 42), "42")


class TestVariablePropertyNoEmptyDefault(unittest.TestCase):
    """测试 _format_variable_property 不产生 '= ;' 输出。"""

    def test_none_default_no_equals(self) -> None:
        """None 默认值不应输出 '= ;'。"""
        prop = _make_variable_property("Speed", "float", default_value=None)
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertNotIn("= ;", decl_line)
        self.assertNotIn("= ", decl_line)
        self.assertTrue(decl_line.strip().endswith(";"))

    def test_empty_string_default_no_equals(self) -> None:
        """空字符串默认值不应输出 '= ;'。"""
        prop = _make_variable_property("Name", "FString", default_value="")
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertNotIn("= ;", decl_line)
        self.assertNotIn("= ", decl_line)

    def test_whitespace_default_no_equals(self) -> None:
        """纯空白默认值不应输出 '= ;'。"""
        prop = _make_variable_property("Name", "FString", default_value="   ")
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertNotIn("= ;", decl_line)

    def test_valid_default_has_equals(self) -> None:
        """有效默认值应正常输出 '= value'。"""
        prop = _make_variable_property("Speed", "float", default_value=100.0)
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertIn("= 100.0f", decl_line)
        self.assertTrue(decl_line.strip().endswith(";"))

    def test_valid_bool_default_has_equals(self) -> None:
        """有效 bool 默认值应正常输出。"""
        prop = _make_variable_property("bActive", "bool", default_value=True)
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertIn("= true", decl_line)

    def test_valid_int_default_has_equals(self) -> None:
        """有效 int 默认值应正常输出。"""
        prop = _make_variable_property("Count", "int32", default_value=42)
        lines = _format_variable_property(prop)
        decl_line = lines[-1]
        self.assertIn("= 42", decl_line)


if __name__ == "__main__":
    unittest.main()


# ==============================================================================
# 以下来自 test_cpp_wrapper_nesting.py
# ==============================================================================

"""测试 _strip_function_wrapper 函数和函数体包裹剥离逻辑。

验证：
- 包含完整函数定义的 body_text 不会导致嵌套
- 纯语句体的 body_text 正常输出
- 空 body_text 不崩溃
- 各种边界情况
"""

from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppCallParameter,
    CppMethodIR,
)
from uasset_read.cpp_gen.formatters.cpp_function_body_formatter import (
    _strip_function_wrapper,
    format_cpp_function_body,
)


# ============================================================================
# 辅助工厂
# ============================================================================

def _make_wrapper_method(
    cpp_name: str = "ExecuteUbergraph",
    return_type: str = "void",
    body: list | None = None,
    body_text: str | None = None,
) -> CppMethodIR:
    """创建测试用 CppMethodIR 实例（用于 wrapper nesting 测试）。"""
    return CppMethodIR(
        cpp_name=cpp_name,
        return_type=return_type,
        parameters=[CppCallParameter("EntryPoint", "int32", "input")],
        ufunction_specifiers=[],
        is_override=False,
        body=body or [],
        body_text=body_text,
    )


# ============================================================================
# _strip_function_wrapper 单元测试
# ============================================================================

class TestStripFunctionWrapper:
    """_strip_function_wrapper 剥离逻辑测试。"""

    def test_full_function_def_stripped(self):
        """完整函数定义应被剥离，只返回函数体内容。"""
        text = (
            "void UMyClass::ExecuteUbergraph(int32 EntryPoint)\n"
            "{\n"
            "    DoSomething();\n"
            "    DoMore();\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == "DoSomething();\nDoMore();"

    def test_full_def_with_pointer_return(self):
        """返回指针类型的函数定义应被剥离。"""
        text = (
            "UObject* UMyClass::GetTarget() const\n"
            "{\n"
            "    return Target;\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == "return Target;"

    def test_body_only_passthrough(self):
        """纯语句体应原样返回，不做任何处理。"""
        text = "DoSomething();\nDoMore();"
        result = _strip_function_wrapper(text)
        assert result == text

    def test_empty_text(self):
        """空字符串不应崩溃。"""
        result = _strip_function_wrapper("")
        assert result == ""

    def test_none_like_empty(self):
        """空白字符串不应崩溃。"""
        result = _strip_function_wrapper("   \n  \n  ")
        assert result == "   \n  \n  "

    def test_control_flow_not_stripped(self):
        """if/for/while 等控制流语句不应被误判为函数签名。"""
        text = (
            "if (bIsActive)\n"
            "{\n"
            "    Activate();\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == text

    def test_for_loop_not_stripped(self):
        """for 循环不应被误判。"""
        text = (
            "for (int i = 0; i < Count; ++i)\n"
            "{\n"
            "    Process(i);\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == text

    def test_while_loop_not_stripped(self):
        """while 循环不应被误判。"""
        text = (
            "while (HasMore())\n"
            "{\n"
            "    Next();\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == text

    def test_switch_not_stripped(self):
        """switch 语句不应被误判。"""
        text = (
            "switch (Type)\n"
            "{\n"
            "    case 0: break;\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == text

    def test_no_closing_brace_passthrough(self):
        """缺少闭合花括号的文本应原样返回。"""
        text = (
            "void UMyClass::ExecuteUbergraph(int32 EntryPoint)\n"
            "{\n"
            "    DoSomething();"
        )
        result = _strip_function_wrapper(text)
        assert result == text

    def test_no_opening_brace_passthrough(self):
        """缺少开花括号的文本应原样返回。"""
        text = (
            "void UMyClass::ExecuteUbergraph(int32 EntryPoint)\n"
            "    DoSomething();\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == text

    def test_single_line_passthrough(self):
        """单行文本应原样返回。"""
        text = "DoSomething();"
        result = _strip_function_wrapper(text)
        assert result == text

    def test_tab_indent_stripped(self):
        """tab 缩进应被正确剥离。"""
        text = (
            "void UMyClass::Tick(float DeltaTime)\n"
            "{\n"
            "\tUpdatePosition(DeltaTime);\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == "UpdatePosition(DeltaTime);"

    def test_mixed_indent_stripped(self):
        """部分缩进、部分无缩进的函数体应正确处理。"""
        text = (
            "void UMyClass::Init()\n"
            "{\n"
            "    Setup();\n"
            "Teardown();\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == "Setup();\nTeardown();"

    def test_blank_lines_between_sig_and_brace(self):
        """签名和花括号之间有空行时仍应正确剥离。"""
        text = (
            "void UMyClass::ExecuteUbergraph(int32 EntryPoint)\n"
            "\n"
            "{\n"
            "    DoSomething();\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == "DoSomething();"

    def test_complex_return_type(self):
        """返回类型含多个标识符（如 const FVector&）应被正确识别。"""
        text = (
            "const FVector& UMyClass::GetLocation() const\n"
            "{\n"
            "    return CachedLocation;\n"
            "}"
        )
        result = _strip_function_wrapper(text)
        assert result == "return CachedLocation;"

    def test_multiline_body_preserved(self):
        """多行函数体内容应完整保留。"""
        body_lines = ["Init();", "SetOwner(this);", "Activate(true);", "MarkDirty();"]
        text = (
            "void UMyClass::Setup()\n"
            "{\n"
            + "".join(f"    {line}\n" for line in body_lines)
            + "}"
        )
        result = _strip_function_wrapper(text)
        expected = "\n".join(body_lines)
        assert result == expected


# ============================================================================
# format_cpp_function_body 集成测试
# ============================================================================

class TestFormatCppFunctionBody:
    """format_cpp_function_body 函数集成测试。"""

    def test_wrapped_body_text_no_nesting(self):
        """body_text 包含完整函数定义时，输出不应嵌套。"""
        method = _make_wrapper_method(
            body_text=(
                "void UMyClass::ExecuteUbergraph(int32 EntryPoint)\n"
                "{\n"
                "    DoSomething();\n"
                "}"
            )
        )
        result = format_cpp_function_body(method)

        # 不应包含两层签名
        assert result.count("void") == 1, f"输出不应嵌套函数签名:\n{result}"
        assert result.count("ExecuteUbergraph") == 1
        assert "DoSomething();" in result

    def test_plain_body_text_works_normally(self):
        """纯语句体的 body_text 应正常输出。"""
        method = _make_wrapper_method(
            body_text="DoSomething();\nDoMore();"
        )
        result = format_cpp_function_body(method)

        # format_cpp_function_body 使用 cpp_name（不含类名前缀）
        assert "void ExecuteUbergraph(int32 EntryPoint)" in result
        assert "DoSomething();" in result
        assert "DoMore();" in result

    def test_empty_body_text_no_crash(self):
        """空 body_text 不应崩溃。"""
        method = _make_wrapper_method(body_text="")
        result = format_cpp_function_body(method)

        assert "void ExecuteUbergraph(int32 EntryPoint)" in result
        assert result.strip().endswith("}")

    def test_none_body_text_no_crash(self):
        """body_text 为 None 且 body 为空时不应崩溃。"""
        method = _make_wrapper_method(body_text=None)
        result = format_cpp_function_body(method)

        assert "void ExecuteUbergraph(int32 EntryPoint)" in result
        assert result.strip().endswith("}")

    def test_body_statements_take_priority(self):
        """结构化 body 优先于 body_text。"""
        from uasset_read.cpp_gen.formatters import CppCallStmt

        stmt = CppCallStmt(
            method_name="Initialize",
            target="this",
            args=["true"],
        )
        method = _make_wrapper_method(
            body=[stmt],
            body_text="OldText();",
        )
        result = format_cpp_function_body(method)

        assert "Initialize(true);" in result
        assert "OldText();" not in result

    def test_wrapped_body_with_pointer_return(self):
        """返回指针类型的包裹 body_text 应正确剥离。"""
        method = _make_wrapper_method(
            cpp_name="GetTarget",
            return_type="UObject*",
            body_text=(
                "UObject* UMyClass::GetTarget()\n"
                "{\n"
                "    return CachedTarget;\n"
                "}"
            )
        )
        result = format_cpp_function_body(method)

        # 只应出现一次签名
        assert "UObject*" in result
        assert "return CachedTarget;" in result
        # 不应有嵌套的花括号块
        brace_count = result.count("{")
        assert brace_count == 1, f"应只有一个花括号块，实际 {brace_count}:\n{result}"

    def test_control_flow_body_not_stripped(self):
        """控制流语句开头的 body_text 不应被剥离。"""
        method = _make_wrapper_method(
            body_text=(
                "if (bIsActive)\n"
                "{\n"
                "    Activate();\n"
                "}"
            )
        )
        result = format_cpp_function_body(method)

        assert "if (bIsActive)" in result
        assert "Activate();" in result
