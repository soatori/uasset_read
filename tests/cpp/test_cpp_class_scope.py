"""C++ 类作用域（ClassName::Method）测试。

验证 .cpp 实现文件中的方法定义使用 ClassName::MethodName 格式，
而 .h 头文件声明不使用该前缀。
"""
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
