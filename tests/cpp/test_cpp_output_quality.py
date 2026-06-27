"""C++ 输出质量集成测试。

使用 mock 蓝图数据验证 cpp_gen 模块生成的 C++ 代码质量：
- 头文件宏结构（UCLASS/UPROPERTY/UFUNCTION）
- 函数体完整性
- 变量默认值格式化
- 类名前缀约定
- 占位符比例控制
"""
from __future__ import annotations

import unittest
from typing import List
from unittest.mock import MagicMock

from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppCallParameter,
    CppClassIR,
    CppHeaderMeta,
    CppMethodIR,
    CppProperty,
)
from uasset_read.cpp_gen.formatters.cpp_header_formatter import format_cpp_header
from uasset_read.cpp_gen.formatters.cpp_function_body_formatter import (
    format_cpp_function_body,
    format_full_cpp_implementation,
)
from uasset_read.cpp_gen.cpp_default_value_formatter import format_cpp_default_value
from uasset_read.cpp_gen.cpp_type_mapper import infer_class_prefix, ue_package_path_to_cpp_class


# ============================================================================
# Mock 工厂函数
# ============================================================================

def _make_property(
    name: str,
    cpp_type: str,
    category: str = "variable",
    marks: List[str] | None = None,
    default_value=None,
) -> CppProperty:
    """构建 CppProperty 测试对象。"""
    if marks is None:
        marks = ["EditAnywhere", "BlueprintReadWrite"]
    return CppProperty(
        cpp_type=cpp_type,
        name=name,
        uproperty_marks=marks,
        category=category,
        default_value=default_value,
    )


def _make_method(
    name: str,
    return_type: str = "void",
    parameters: List[CppCallParameter] | None = None,
    specifiers: List[str] | None = None,
    is_override: bool = False,
    body_text: str | None = None,
    body: list | None = None,
) -> CppMethodIR:
    """构建 CppMethodIR 测试对象。"""
    if parameters is None:
        parameters = []
    if specifiers is None:
        specifiers = ["BlueprintCallable"]
    return CppMethodIR(
        cpp_name=name,
        return_type=return_type,
        parameters=parameters,
        ufunction_specifiers=specifiers,
        is_override=is_override,
        body=body or [],
        body_text=body_text,
    )


def _build_actor_blueprint_ir() -> CppClassIR:
    """构建一个完整的 Actor 派生蓝图 CppClassIR（含组件、变量、方法）。"""
    properties = [
        _make_property(
            "Mesh",
            "UStaticMeshComponent*",
            category="component",
            marks=["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
        ),
        _make_property(
            "MoveSpeed",
            "float",
            category="variable",
            marks=["EditAnywhere", "BlueprintReadWrite"],
            default_value=600.0,
        ),
        _make_property(
            "bCanJump",
            "bool",
            category="variable",
            marks=["EditAnywhere", "BlueprintReadWrite"],
            default_value=True,
        ),
        _make_property(
            "PlayerName",
            "FString",
            category="variable",
            marks=["EditAnywhere", "BlueprintReadWrite"],
            default_value="Player",
        ),
    ]

    methods = [
        _make_method(
            "BeginPlay",
            return_type="void",
            specifiers=[],
            is_override=True,
            body_text="Super::BeginPlay();\nUE_LOG(LogTemp, Log, TEXT(\"BeginPlay\"));",
        ),
        _make_method(
            "Jump",
            return_type="void",
            parameters=[
                CppCallParameter(name="Height", cpp_type="float", direction="input"),
            ],
            specifiers=["BlueprintCallable"],
            body_text="if (bCanJump)\n{\n    LaunchCharacter(FVector(0, 0, Height), false, true);\n}",
        ),
    ]

    header_meta = CppHeaderMeta.build_from_parent("AActor", "ABP_TestCharacter")

    return CppClassIR(
        name="ABP_TestCharacter",
        parent_class="AActor",
        header_meta=header_meta,
        properties=properties,
        methods=methods,
        constructor={
            "component_creations": ["Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT(\"Mesh\"));"],
            "component_assignments": [],
            "default_values": ["MoveSpeed = 600.f;", "bCanJump = true;", 'PlayerName = TEXT("Player");'],
        },
    )


# ============================================================================
# 测试用例
# ============================================================================

class TestBlueprintCppHeader(unittest.TestCase):
    """测试蓝图资产生成的 C++ 头文件包含必要宏。"""

    def test_blueprint_cpp_header(self) -> None:
        """验证 .h 输出包含 UCLASS、UPROPERTY、UFUNCTION 宏。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)

        # UCLASS 宏
        self.assertIn("UCLASS(", header, "头文件缺少 UCLASS 宏")

        # UPROPERTY 宏（每个属性一个）
        uproperty_count = header.count("UPROPERTY(")
        self.assertGreaterEqual(
            uproperty_count, 4,
            f"期望至少 4 个 UPROPERTY 宏，实际 {uproperty_count}",
        )

        # UFUNCTION 宏（BlueprintCallable 方法）
        ufunction_count = header.count("UFUNCTION(")
        self.assertGreaterEqual(
            ufunction_count, 1,
            f"期望至少 1 个 UFUNCTION 宏，实际 {ufunction_count}",
        )

        # GENERATED_BODY()
        self.assertIn("GENERATED_BODY()", header, "头文件缺少 GENERATED_BODY()")

        # class 声明
        self.assertIn("class ABP_TestCharacter : public AActor", header)

    def test_header_has_pragma_once(self) -> None:
        """验证 #pragma once 存在。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        self.assertIn("#pragma once", header)

    def test_header_has_core_minimal(self) -> None:
        """验证包含 CoreMinimal.h。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        self.assertIn('#include "CoreMinimal.h"', header)

    def test_header_has_generated_include(self) -> None:
        """验证 .generated.h 包含在末尾。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        self.assertIn(".generated.h", header)

    def test_header_public_section(self) -> None:
        """验证 public: 段存在。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        self.assertIn("public:", header)

    def test_header_protected_section(self) -> None:
        """验证 protected: 段存在。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        self.assertIn("protected:", header)

    def test_header_component_marks(self) -> None:
        """验证组件属性使用 VisibleAnywhere + Instanced 标记。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        # 组件属性应有 VisibleAnywhere 和 Instanced
        self.assertIn("VisibleAnywhere", header)
        self.assertIn("Instanced", header)


class TestFunctionBodyNotEmpty(unittest.TestCase):
    """测试函数体非空。"""

    def test_function_body_not_empty(self) -> None:
        """验证生成的函数体包含实际代码。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        cpp = format_full_cpp_implementation(ir)

        # .cpp 实现文件应包含至少一个函数体
        self.assertGreater(
            len(cpp.split("\n")),
            5,
            ".cpp 实现文件过短，可能缺少函数体",
        )

        # 函数体中应有实际 C++ 语句（非空大括号块）
        self.assertIn("Super::BeginPlay()", cpp)
        self.assertIn("LaunchCharacter", cpp)

    def test_body_text_injected(self) -> None:
        """验证 body_text 被正确渲染到函数实现中。"""
        method = _make_method(
            "Tick",
            body_text="Super::Tick(DeltaTime);\nUpdateMovement(DeltaTime);",
        )
        body = format_cpp_function_body(method)

        self.assertIn("Super::Tick(DeltaTime)", body)
        self.assertIn("UpdateMovement(DeltaTime)", body)

    def test_empty_body_renders_braces(self) -> None:
        """验证无 body 的方法仍生成有效的大括号结构。"""
        method = _make_method("DoNothing")
        body = format_cpp_function_body(method)

        # 至少有签名行、{、}
        lines = body.strip().split("\n")
        self.assertTrue(lines[0].startswith("void DoNothing"))
        self.assertIn("{", body)
        self.assertIn("}", body)


class TestVariableDefaultValue(unittest.TestCase):
    """测试变量默认值格式化。"""

    def test_variable_default_value(self) -> None:
        """验证默认值正确格式化。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)

        # float 默认值应包含 f 后缀
        self.assertIn("MoveSpeed = ", header)
        self.assertTrue(
            "600.f" in header or "600.0f" in header,
            f"MoveSpeed 默认值应为 600.f 或 600.0f 格式",
        )

        # bool 默认值应为 true/false
        self.assertIn("bCanJump = true", header)

        # FString 默认值应使用 TEXT() 宏
        self.assertIn('PlayerName = TEXT("Player")', header)

    def test_format_cpp_default_value_float(self) -> None:
        """验证 float 默认值格式。"""
        self.assertEqual(format_cpp_default_value(100.0, "float"), "100.f")
        self.assertEqual(format_cpp_default_value(400.12, "float"), "400.12f")
        self.assertEqual(format_cpp_default_value(0.0, "float"), "0.f")

    def test_format_cpp_default_value_bool(self) -> None:
        """验证 bool 默认值格式。"""
        self.assertEqual(format_cpp_default_value(True, "bool"), "true")
        self.assertEqual(format_cpp_default_value(False, "bool"), "false")
        self.assertEqual(format_cpp_default_value(1, "bool"), "true")
        self.assertEqual(format_cpp_default_value(0, "bool"), "false")

    def test_format_cpp_default_value_int(self) -> None:
        """验证 int 默认值格式。"""
        self.assertEqual(format_cpp_default_value(42, "int32"), "42")
        self.assertEqual(format_cpp_default_value(0, "int"), "0")
        self.assertEqual(format_cpp_default_value(255, "uint8"), "255")

    def test_format_cpp_default_value_string(self) -> None:
        """验证 FString/FName 默认值格式。"""
        self.assertEqual(
            format_cpp_default_value("hello", "FString"),
            'TEXT("hello")',
        )
        self.assertEqual(
            format_cpp_default_value("test", "FName"),
            'TEXT("test")',
        )

    def test_format_cpp_default_value_ftext(self) -> None:
        """验证 FText 默认值格式。"""
        result = format_cpp_default_value("hello", "FText")
        self.assertIn("FText::FromString", result)
        self.assertIn("hello", result)

    def test_format_cpp_default_value_none(self) -> None:
        """验证 None 默认值返回空字符串。"""
        self.assertEqual(format_cpp_default_value(None, "float"), "")

    def test_format_cpp_default_value_enum(self) -> None:
        """验证枚举默认值直接使用值。"""
        self.assertEqual(
            format_cpp_default_value("FirstPerson", "EFirstPersonPrimitiveType"),
            "FirstPerson",
        )

    def test_format_cpp_default_value_double(self) -> None:
        """验证 double 默认值无后缀。"""
        self.assertEqual(format_cpp_default_value(3.14, "double"), "3.14")


class TestClassNamePrefix(unittest.TestCase):
    """测试类名前缀约定。"""

    def test_class_name_prefix(self) -> None:
        """验证 Actor 派生类使用 A 前缀。"""
        ir = _build_actor_blueprint_ir()

        # 类名应以 A 开头（Actor 派生）
        self.assertTrue(
            ir.name.startswith("A"),
            f"Actor 派生类 '{ir.name}' 应以 A 开头",
        )

        # 父类应为 AActor
        self.assertEqual(ir.parent_class, "AActor")

    def test_infer_class_prefix_actor(self) -> None:
        """验证 Actor 父类推导 A 前缀。"""
        self.assertEqual(infer_class_prefix("ACharacter"), "A")
        self.assertEqual(infer_class_prefix("AActor"), "A")
        self.assertEqual(infer_class_prefix("APawn"), "A")

    def test_infer_class_prefix_uobject(self) -> None:
        """验证 UObject 父类推导 U 前缀。"""
        self.assertEqual(infer_class_prefix("USceneComponent"), "U")
        self.assertEqual(infer_class_prefix("UObject"), "U")
        self.assertEqual(infer_class_prefix("UActorComponent"), "U")

    def test_infer_class_prefix_struct(self) -> None:
        """验证结构体父类推导 F 前缀。"""
        self.assertEqual(infer_class_prefix("FVector"), "F")
        self.assertEqual(infer_class_prefix("FTransform"), "F")

    def test_infer_class_prefix_enum(self) -> None:
        """验证枚举父类推导 E 前缀。"""
        self.assertEqual(infer_class_prefix("EDirection"), "E")

    def test_infer_class_prefix_interface(self) -> None:
        """验证接口父类推导 I 前缀。"""
        self.assertEqual(infer_class_prefix("IInteractable"), "I")

    def test_ue_package_path_to_cpp_class_actor(self) -> None:
        """验证 UE 包路径 Actor → C++ 类名。"""
        self.assertEqual(
            ue_package_path_to_cpp_class("/Script/Engine.Character"),
            "ACharacter",
        )
        self.assertEqual(
            ue_package_path_to_cpp_class("/Script/Engine.Actor"),
            "AActor",
        )

    def test_ue_package_path_to_cpp_class_component(self) -> None:
        """验证 UE 包路径 Component → C++ 类名。"""
        self.assertEqual(
            ue_package_path_to_cpp_class("/Script/Engine.SceneComponent"),
            "USceneComponent",
        )

    def test_header_reflects_prefix(self) -> None:
        """验证 .h 输出中类名与前缀一致。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)

        # class 声明中的类名应以 A 开头
        for line in header.split("\n"):
            if line.strip().startswith("class "):
                self.assertTrue(
                    "ABP_TestCharacter" in line,
                    f"class 声明行应包含正确的 A 前缀类名: {line}",
                )
                break

    def test_uobject_parent_gets_u_prefix(self) -> None:
        """验证 UObject 派生的蓝图类使用 U 前缀。"""
        ir = CppClassIR(
            name="UMyComponent",
            parent_class="UActorComponent",
            header_meta=CppHeaderMeta.build_from_parent("UActorComponent", "UMyComponent"),
            properties=[],
            methods=[],
        )
        header = format_cpp_header(ir)

        # 以 U 开头
        self.assertTrue(ir.name.startswith("U"))
        self.assertIn("class UMyComponent : public UActorComponent", header)


class TestNoFunctionPlaceholder(unittest.TestCase):
    """测试输出中 Function_ 占位符比例 < 10%。"""

    def test_no_function_placeholder(self) -> None:
        """验证输出中 Function_ 占位符比例 < 10%。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        cpp = format_full_cpp_implementation(ir)
        combined = header + cpp

        total_lines = len(combined.splitlines())
        placeholder_lines = sum(
            1 for line in combined.splitlines() if "Function_" in line
        )

        if total_lines == 0:
            ratio = 0.0
        else:
            ratio = placeholder_lines / total_lines

        self.assertLess(
            ratio,
            0.10,
            f"Function_ 占位符比例 {ratio:.2%} 超过 10% "
            f"({placeholder_lines}/{total_lines} 行)",
        )

    def test_function_placeholder_not_in_method_names(self) -> None:
        """验证方法名中不包含 Function_ 前缀。"""
        ir = _build_actor_blueprint_ir()

        for method in ir.methods:
            self.assertNotIn(
                "Function_",
                method.cpp_name,
                f"方法名 '{method.cpp_name}' 不应包含 Function_ 前缀",
            )

    def test_placeholder_in_body_text(self) -> None:
        """验证 body_text 中的 Function_ 引用不计入方法名质量。"""
        # body_text 中可能有 Function_ 引用（如 Kismet 反编译输出）
        # 但方法声明本身不应包含
        method = _make_method(
            "CustomEvent",
            body_text="Function_SomeInternalFunc();",
        )
        self.assertNotIn("Function_", method.cpp_name)

    def test_mixed_output_low_placeholder_ratio(self) -> None:
        """验证多个蓝图的混合输出占位符比例仍低于 10%。"""
        irs = [
            _build_actor_blueprint_ir(),
            CppClassIR(
                name="UMyComponent",
                parent_class="UActorComponent",
                header_meta=CppHeaderMeta.build_from_parent("UActorComponent", "UMyComponent"),
                properties=[
                    _make_property("Value", "int32", default_value=42),
                ],
                methods=[
                    _make_method("GetValue", return_type="int32", body_text="return Value;"),
                ],
            ),
        ]

        combined = ""
        for ir in irs:
            combined += format_cpp_header(ir) + "\n"
            combined += format_full_cpp_implementation(ir) + "\n"

        total_lines = len(combined.splitlines())
        placeholder_lines = sum(
            1 for line in combined.splitlines() if "Function_" in line
        )

        ratio = placeholder_lines / total_lines if total_lines > 0 else 0.0
        self.assertLess(
            ratio,
            0.10,
            f"混合输出 Function_ 占位符比例 {ratio:.2%} 超过 10% "
            f"({placeholder_lines}/{total_lines} 行)",
        )


# ============================================================================
# 额外质量断言测试
# ============================================================================

class TestCppOutputStructure(unittest.TestCase):
    """测试 C++ 输出的整体结构质量。"""

    def test_header_terminates_with_semicolon(self) -> None:
        """验证 .h 文件以 }; 结尾（类定义闭合）。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        stripped_lines = [l for l in header.splitlines() if l.strip()]
        self.assertTrue(
            stripped_lines[-1].endswith("};"),
            f".h 最后一行应以 }}; 结尾: {stripped_lines[-1]}",
        )

    def test_cpp_starts_with_filename_comment(self) -> None:
        """验证 .cpp 以文件名注释开头。"""
        ir = _build_actor_blueprint_ir()
        cpp = format_full_cpp_implementation(ir)
        first_line = cpp.splitlines()[0]
        self.assertTrue(
            first_line.startswith("//"),
            f".cpp 首行应为注释: {first_line}",
        )

    def test_cpp_includes_own_header(self) -> None:
        """验证 .cpp 包含自身 .h 头文件。"""
        ir = _build_actor_blueprint_ir()
        cpp = format_full_cpp_implementation(ir)
        self.assertIn(f'#include "{ir.name}.h"', cpp)

    def test_all_methods_have_signatures(self) -> None:
        """验证所有方法在 .h 中都有声明。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)

        for method in ir.methods:
            self.assertIn(
                method.cpp_name,
                header,
                f"方法 '{method.cpp_name}' 未出现在 .h 声明中",
            )

    def test_constructor_declaration_exists(self) -> None:
        """验证构造函数声明存在。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        self.assertIn("ABP_TestCharacter();", header)


if __name__ == "__main__":
    unittest.main()
