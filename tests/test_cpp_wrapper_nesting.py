"""测试 _strip_function_wrapper 函数和函数体包裹剥离逻辑。

验证：
- 包含完整函数定义的 body_text 不会导致嵌套
- 纯语句体的 body_text 正常输出
- 空 body_text 不崩溃
- 各种边界情况
"""
from __future__ import annotations

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

def _make_method(
    cpp_name: str = "ExecuteUbergraph",
    return_type: str = "void",
    body: list | None = None,
    body_text: str | None = None,
) -> CppMethodIR:
    """创建测试用 CppMethodIR 实例。"""
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
        method = _make_method(
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
        method = _make_method(
            body_text="DoSomething();\nDoMore();"
        )
        result = format_cpp_function_body(method)

        # format_cpp_function_body 使用 cpp_name（不含类名前缀）
        assert "void ExecuteUbergraph(int32 EntryPoint)" in result
        assert "DoSomething();" in result
        assert "DoMore();" in result

    def test_empty_body_text_no_crash(self):
        """空 body_text 不应崩溃。"""
        method = _make_method(body_text="")
        result = format_cpp_function_body(method)

        assert "void ExecuteUbergraph(int32 EntryPoint)" in result
        assert result.strip().endswith("}")

    def test_none_body_text_no_crash(self):
        """body_text 为 None 且 body 为空时不应崩溃。"""
        method = _make_method(body_text=None)
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
        method = _make_method(
            body=[stmt],
            body_text="OldText();",
        )
        result = format_cpp_function_body(method)

        assert "Initialize(true);" in result
        assert "OldText();" not in result

    def test_wrapped_body_with_pointer_return(self):
        """返回指针类型的包裹 body_text 应正确剥离。"""
        method = _make_method(
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
        method = _make_method(
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
