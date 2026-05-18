"""单元测试：CppFunctionBodyFormatter — CppStatement → .cpp 文本。"""
import pytest

from uasset_read.cpp_gen.formatters import (
    CppAssignmentStmt,
    CppCallParameter,
    CppCallStmt,
    CppClassIR,
    CppHeaderMeta,
    CppIfStmt,
    CppInlineExprStmt,
    CppMethodIR,
)
from uasset_read.cpp_gen.formatters.cpp_function_body_formatter import (
    format_cpp_function_body,
    format_full_cpp_implementation,
)


def _make_method_ir(name: str, params: list = None, body: list = None) -> CppMethodIR:
    """辅助函数：创建测试用 CppMethodIR。"""
    return CppMethodIR(
        cpp_name=name,
        return_type="void",
        parameters=[
            CppCallParameter(name=p[0], cpp_type=p[1], direction="input")
            for p in (params or [])
        ],
        ufunction_specifiers=[],
        is_override=False,
        body=body or [],
    )


# ============================================================================
# Task 1: format_cpp_function_body — 单函数体渲染
# ============================================================================

class TestFormatCppFunctionBody:

    def test_importable(self):
        """format_cpp_function_body 可导入。"""
        from uasset_read.cpp_gen.formatters import format_cpp_function_body
        assert callable(format_cpp_function_body)

    def test_format_jump_function_body(self):
        """Jump() 函数体 → Super::Jump()。"""
        method_ir = _make_method_ir(
            "Jump",
            body=[CppCallStmt(target="Super", method_name="Jump", args=[])],
        )
        result = format_cpp_function_body(method_ir)
        assert "void Jump()" in result
        assert "{" in result
        assert "Super::Jump();" in result
        assert "}" in result

    def test_format_stop_jumping_function_body(self):
        """StopJumping() → Super::StopJumping()。"""
        method_ir = _make_method_ir(
            "StopJumping",
            body=[CppCallStmt(target="Super", method_name="StopJumping", args=[])],
        )
        result = format_cpp_function_body(method_ir)
        assert "Super::StopJumping();" in result

    def test_format_aim_function_body(self):
        """Aim() → 含 AddControllerYawInput 和 AddControllerPitchInput。"""
        method_ir = _make_method_ir(
            "Aim",
            params=[("Yaw", "float"), ("Pitch", "float")],
            body=[
                CppCallStmt(target="this", method_name="AddControllerYawInput", args=["Yaw"]),
                CppCallStmt(target="this", method_name="AddControllerPitchInput", args=["Pitch"]),
            ],
        )
        result = format_cpp_function_body(method_ir)
        assert "void Aim(float Yaw, float Pitch)" in result
        assert "AddControllerYawInput(Yaw);" in result
        assert "AddControllerPitchInput(Pitch);" in result

    def test_format_move_function_body(self):
        """Move() → 含内联表达式 GetActorRightVector()。"""
        method_ir = _make_method_ir(
            "Move",
            params=[("LeftRight", "double"), ("ForwardBackward", "double")],
            body=[
                CppCallStmt(
                    target="this",
                    method_name="AddMovementInput",
                    args=["GetActorRightVector()", "LeftRight"],
                ),
                CppCallStmt(
                    target="this",
                    method_name="AddMovementInput",
                    args=["GetActorForwardVector()", "ForwardBackward"],
                ),
            ],
        )
        result = format_cpp_function_body(method_ir)
        assert "AddMovementInput(GetActorRightVector(), LeftRight);" in result
        assert "AddMovementInput(GetActorForwardVector(), ForwardBackward);" in result

    def test_format_if_statement(self):
        """IfStmt → `if (condition) { ... }` 格式文本。"""
        inner = CppCallStmt(target="this", method_name="DoSomething", args=[])
        method_ir = _make_method_ir(
            "TestIf",
            body=[CppIfStmt(condition="bActive", then_body=[inner])],
        )
        result = format_cpp_function_body(method_ir)
        assert "if (bActive) {" in result
        assert "DoSomething();" in result

    def test_format_if_else_statement(self):
        """IfStmt with else_body → `if (condition) { ... } else { ... }`。"""
        method_ir = _make_method_ir(
            "TestIfElse",
            body=[
                CppIfStmt(
                    condition="x > 0",
                    then_body=[CppCallStmt(target="this", method_name="Positive", args=[])],
                    else_body=[CppCallStmt(target="this", method_name="Negative", args=[])],
                )
            ],
        )
        result = format_cpp_function_body(method_ir)
        assert "if (x > 0) {" in result
        assert "} else {" in result
        assert "Positive();" in result
        assert "Negative();" in result

    def test_format_assignment_statement(self):
        """AssignmentStmt → `lhs = rhs;`。"""
        method_ir = _make_method_ir(
            "TestAssign",
            body=[CppAssignmentStmt(lhs="Result", rhs="A + B", cpp_type="float")],
        )
        result = format_cpp_function_body(method_ir)
        assert "Result = A + B;" in result

    def test_indentation_is_4_spaces(self):
        """缩进为 4 空格。"""
        method_ir = _make_method_ir(
            "TestIndent",
            body=[CppCallStmt(target="this", method_name="Foo", args=[])],
        )
        result = format_cpp_function_body(method_ir)
        # 函数体语句应该有 4 空格缩进
        assert "    Foo();" in result

    def test_super_call_format(self):
        """Super 调用格式正确（`Super::` 前缀）。"""
        method_ir = _make_method_ir(
            "BeginPlay",
            body=[CppCallStmt(target="Super", method_name="BeginPlay", args=[])],
        )
        result = format_cpp_function_body(method_ir)
        assert "Super::BeginPlay();" in result

    def test_empty_body(self):
        """空 body → 只有签名和大括号。"""
        method_ir = _make_method_ir("Empty")
        result = format_cpp_function_body(method_ir)
        assert "void Empty()" in result
        assert "{}" not in result  # 大括号分行
        assert "{" in result
        assert "}" in result

    def test_inline_expr_stmt_not_rendered(self):
        """CppInlineExprStmt 不独立成行。"""
        method_ir = _make_method_ir(
            "TestInline",
            body=[CppInlineExprStmt(expression="GetActorRightVector()")],
        )
        result = format_cpp_function_body(method_ir)
        assert "GetActorRightVector()" not in result  # inline expr 不独立输出


# ============================================================================
# Task 2: format_full_cpp_implementation — 完整 .cpp 文件
# ============================================================================

class TestFormatFullCppImplementation:

    def test_importable(self):
        """format_full_cpp_implementation 可导入。"""
        from uasset_read.cpp_gen.formatters import format_full_cpp_implementation
        assert callable(format_full_cpp_implementation)

    def test_output_starts_with_include(self):
        """输出以 #include 开头（含注释）。"""
        ir = CppClassIR(
            name="ATestCharacter",
            parent_class="ACharacter",
            header_meta=CppHeaderMeta(),
            methods=[
                _make_method_ir("Jump", body=[CppCallStmt(target="Super", method_name="Jump")]),
            ],
        )
        result = format_full_cpp_implementation(ir)
        assert "// ATestCharacter.cpp" in result
        assert '#include "ATestCharacter.h"' in result

    def test_format_full_implementation(self):
        """完整 CppClassIR → .cpp 文本。"""
        ir = CppClassIR(
            name="ABP_FirstPerson",
            parent_class="ACharacter",
            header_meta=CppHeaderMeta(),
            methods=[
                _make_method_ir(
                    "Jump",
                    body=[CppCallStmt(target="Super", method_name="Jump")],
                ),
                _make_method_ir(
                    "Aim",
                    params=[("Yaw", "float"), ("Pitch", "float")],
                    body=[
                        CppCallStmt(target="this", method_name="AddControllerYawInput", args=["Yaw"]),
                        CppCallStmt(target="this", method_name="AddControllerPitchInput", args=["Pitch"]),
                    ],
                ),
            ],
        )
        result = format_full_cpp_implementation(ir)
        assert "// ABP_FirstPerson.cpp" in result
        assert '#include "ABP_FirstPerson.h"' in result
        assert "void Jump()" in result
        assert "void Aim(float Yaw, float Pitch)" in result
        assert "Super::Jump();" in result

    def test_format_empty_class(self):
        """无方法的 CppClassIR → 最小 .cpp。"""
        ir = CppClassIR(
            name="AEmpty",
            parent_class="AActor",
            header_meta=CppHeaderMeta(),
            methods=[],
        )
        result = format_full_cpp_implementation(ir)
        assert "// AEmpty.cpp" in result
        assert '#include "AEmpty.h"' in result
        # 不含任何函数实现
        assert "void" not in result

    def test_methods_separated_by_two_blank_lines(self):
        """方法之间空 2 行。"""
        ir = CppClassIR(
            name="ATwo",
            parent_class="AActor",
            header_meta=CppHeaderMeta(),
            methods=[
                _make_method_ir("Foo", body=[CppCallStmt(target="this", method_name="X")]),
                _make_method_ir("Bar", body=[CppCallStmt(target="this", method_name="Y")]),
            ],
        )
        result = format_full_cpp_implementation(ir)
        assert "\n\n\n" in result  # 方法之间有 2 空行


# ============================================================================
# Task 3: 模块导出集成
# ============================================================================

class TestModuleExports:

    def test_import_format_cpp_function_body(self):
        """from uasset_read.cpp_gen.formatters import format_cpp_function_body 退出 0。"""
        from uasset_read.cpp_gen.formatters import format_cpp_function_body
        assert callable(format_cpp_function_body)

    def test_import_format_full_cpp_implementation(self):
        """from uasset_read.cpp_gen.formatters import format_full_cpp_implementation 退出 0。"""
        from uasset_read.cpp_gen.formatters import format_full_cpp_implementation
        assert callable(format_full_cpp_implementation)

    def test_all_contains_new_symbols(self):
        """__all__ 包含新符号。"""
        from uasset_read.cpp_gen.formatters import __all__
        assert "format_cpp_function_body" in __all__
        assert "format_full_cpp_implementation" in __all__
        assert "CppStatement" in __all__
        assert "CppCallStmt" in __all__
        assert "CppAssignmentStmt" in __all__
        assert "CppIfStmt" in __all__
        assert "CppInlineExprStmt" in __all__
