"""C++ 输出质量与清理器测试 — 合并自 test_cpp_output_quality.py、test_cpp_sanitizer.py 和 test_sanitization.py。

覆盖：C++ 头文件/实现质量、标识符清理、字符串字面量清理、UPROPERTY marks 清理、
Category 清理、MathSimplifier、#include 去重。
"""
from __future__ import annotations

import unittest
from typing import List
from unittest.mock import MagicMock

import pytest

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


# ============================================================================
# #include 去重测试（合并自 test_cpp_include_dedup.py）
# ============================================================================


class TestHeaderIncludesDedup:
    """format_cpp_header 的 include 去重测试。"""

    def test_no_duplicate_includes(self):
        """重复的 include 项在输出中只出现一次。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=[
                '"Engine/Engine.h"',
                '"Engine/Engine.h"',
                '"GameFramework/Character.h"',
                '"GameFramework/Character.h"',
                '"GameFramework/Character.h"',
            ],
            generated_include='"MyClass.generated.h"',
        )
        ir = CppClassIR(
            name="AMyClass",
            parent_class="ACharacter",
            header_meta=meta,
        )

        output = format_cpp_header(ir)

        # 每个 include 应只出现一次
        assert output.count('#include "Engine/Engine.h"') == 1
        assert output.count('#include "GameFramework/Character.h"') == 1

    def test_coreminimal_always_present_once(self):
        """CoreMinimal.h 始终存在且只出现一次。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=['"CoreMinimal.h"'],  # 手动也加了 CoreMinimal
            generated_include='"MyClass.generated.h"',
        )
        ir = CppClassIR(
            name="AMyClass",
            parent_class="ACharacter",
            header_meta=meta,
        )

        output = format_cpp_header(ir)

        # CoreMinimal.h 由 format_cpp_header 硬编码添加，
        # 且 header_meta 中的重复项被 set() 去重
        assert output.count('#include "CoreMinimal.h"') <= 2

    def test_multiple_refs_same_type_one_include(self):
        """多个属性引用同一类型只产生一个 include 行。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=[
                '"Components/StaticMeshComponent.h"',
                '"Components/StaticMeshComponent.h"',
                '"Components/StaticMeshComponent.h"',
            ],
            generated_include='"MyActor.generated.h"',
        )
        ir = CppClassIR(
            name="AMyActor",
            parent_class="AActor",
            header_meta=meta,
        )

        output = format_cpp_header(ir)
        assert output.count('#include "Components/StaticMeshComponent.h"') == 1

    def test_empty_includes_list(self):
        """空 includes 列表不产生额外 include 行（仅 CoreMinimal + generated）。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=[],
            generated_include='"EmptyClass.generated.h"',
        )
        ir = CppClassIR(
            name="AEmptyClass",
            parent_class="AActor",
            header_meta=meta,
        )

        output = format_cpp_header(ir)

        # 只有 CoreMinimal.h 和 .generated.h
        assert '#include "CoreMinimal.h"' in output
        assert '#include "AEmptyClass.generated.h"' in output
        # 不应有其他 include
        include_lines = [l for l in output.splitlines() if l.startswith("#include")]
        assert len(include_lines) == 2

    def test_includes_sorted_and_unique(self):
        """includes 既去重又排序。"""
        meta = CppHeaderMeta(
            pragma_once=True,
            includes=[
                '"Zebra/Z.h"',
                '"Alpha/A.h"',
                '"Zebra/Z.h"',
                '"Beta/B.h"',
                '"Alpha/A.h"',
            ],
            generated_include='"Test.generated.h"',
        )
        ir = CppClassIR(
            name="ATest",
            parent_class="AActor",
            header_meta=meta,
        )

        output = format_cpp_header(ir)
        lines = output.splitlines()

        # 提取 #include 行（排除 CoreMinimal 和 generated）
        include_lines = [
            l for l in lines
            if l.startswith("#include")
            and "CoreMinimal" not in l
            and ".generated.h" not in l
        ]

        assert len(include_lines) == 3
        # 验证排序
        assert '"Alpha/A.h"' in include_lines[0]
        assert '"Beta/B.h"' in include_lines[1]
        assert '"Zebra/Z.h"' in include_lines[2]


if __name__ == "__main__":
    unittest.main()


# ==============================================================================
# 以下来自 test_cpp_sanitizer.py
# ==============================================================================

"""
C++ 标识符清理器单元测试。

测试 sanitize_identifier 的各种边界情况。
"""
import pytest

from uasset_read.cpp_gen.sanitizer import sanitize_identifier


class TestSanitizeIdentifier:
    """sanitize_identifier 函数测试。"""

    # === 验收用例（需求文档明确要求） ===

    def test_spaces_to_underscores(self):
        """空格 → 下划线"""
        assert sanitize_identifier("Target Touch UI") == "Target_Touch_UI"

    def test_special_chars_removed(self):
        """特殊字符被移除"""
        assert sanitize_identifier("MyVar@#$") == "MyVar"

    def test_digit_prefix(self):
        """数字开头 → 前缀 _"""
        assert sanitize_identifier("123Var") == "_123Var"

    def test_empty_string(self):
        """空字符串 → _unnamed"""
        assert sanitize_identifier("") == "_unnamed"

    # === 空格处理 ===

    def test_single_space(self):
        assert sanitize_identifier("My Var") == "My_Var"

    def test_multiple_spaces(self):
        assert sanitize_identifier("A B C D") == "A_B_C_D"

    def test_leading_space(self):
        assert sanitize_identifier(" LeadingSpace") == "_LeadingSpace"

    def test_trailing_space(self):
        assert sanitize_identifier("TrailingSpace ") == "TrailingSpace_"

    def test_only_spaces(self):
        """全是空格 → 全是下划线"""
        assert sanitize_identifier("   ") == "___"

    # === 特殊字符处理 ===

    def test_slash_removed(self):
        """斜杠被移除"""
        assert sanitize_identifier("Left / Right") == "Left__Right"

    def test_at_sign_removed(self):
        assert sanitize_identifier("var@name") == "varname"

    def test_hash_removed(self):
        assert sanitize_identifier("my#var") == "myvar"

    def test_dollar_sign_removed(self):
        assert sanitize_identifier("$price") == "price"

    def test_dot_removed(self):
        assert sanitize_identifier("obj.property") == "objproperty"

    def test_hyphen_removed(self):
        assert sanitize_identifier("my-var") == "myvar"

    def test_parentheses_removed(self):
        assert sanitize_identifier("func(arg)") == "funcarg"

    def test_brackets_removed(self):
        assert sanitize_identifier("arr[0]") == "arr0"

    def test_multiple_special_chars(self):
        assert sanitize_identifier("var!@#$%^&*()") == "var"

    # === 数字开头 ===

    def test_pure_digits(self):
        assert sanitize_identifier("123") == "_123"

    def test_single_digit(self):
        assert sanitize_identifier("0") == "_0"

    def test_digit_then_letter(self):
        assert sanitize_identifier("2DValue") == "_2DValue"

    # === 已经合法的标识符 ===

    def test_valid_identifier(self):
        assert sanitize_identifier("ValidName") == "ValidName"

    def test_valid_with_underscore(self):
        assert sanitize_identifier("_valid") == "_valid"

    def test_valid_with_digits(self):
        assert sanitize_identifier("var123") == "var123"

    def test_valid_mixed(self):
        assert sanitize_identifier("_MyVar_123") == "_MyVar_123"

    # === 边界情况 ===

    def test_none_like_empty(self):
        """空字符串等价于 None"""
        assert sanitize_identifier("") == "_unnamed"

    def test_only_special_chars(self):
        """全是特殊字符 → _unnamed"""
        assert sanitize_identifier("@#$%") == "_unnamed"

    def test_only_special_chars_with_space(self):
        """特殊字符+空格 → 下划线"""
        assert sanitize_identifier("! @") == "_"

    def test_unicode_removed(self):
        """Unicode 字符被移除"""
        assert sanitize_identifier("变量名") == "_unnamed"

    def test_mixed_unicode_and_ascii(self):
        assert sanitize_identifier("My变量Name") == "MyName"

    # === 常见 UE 蓝图名称 ===

    def test_primary_thumbstick(self):
        """UE 常见的摇杆输入名"""
        assert sanitize_identifier("Primary Thumbstick") == "Primary_Thumbstick"

    def test_move_forward(self):
        assert sanitize_identifier("Move Forward") == "Move_Forward"

    def test_target_touch_ui(self):
        """原始 bug 报告的用例"""
        assert sanitize_identifier("Target Touch UI") == "Target_Touch_UI"

    def test_camera_component_name(self):
        """组件名（通常不含空格，但确保安全）"""
        assert sanitize_identifier("FirstPersonCameraComponent") == "FirstPersonCameraComponent"

    # === 通过 sanitize_identifier 直接调用 ===

    def test_sanitize_identifier_direct(self):
        """验证 sanitize_identifier 直接调用"""
        from uasset_read.cpp_gen.sanitizer import sanitize_identifier

        assert sanitize_identifier("Target Touch UI") == "Target_Touch_UI"
        assert sanitize_identifier("MyVar@#$") == "MyVar"
        assert sanitize_identifier("123Var") == "_123Var"
        assert sanitize_identifier("") == "_unnamed"

    # === 通过顶层 __init__ 导出 ===

    def test_exported_from_cpp_gen(self):
        """验证从 cpp_gen 包可导入"""
        from uasset_read.cpp_gen import sanitize_identifier as fn
        assert fn("Test Var") == "Test_Var"

    def test_exported_from_top_level(self):
        """验证从顶层包可导入"""
        from uasset_read import sanitize_identifier as fn
        assert fn("Test Var") == "Test_Var"


# ==============================================================================
# 以下来自 test_sanitization.py
# ==============================================================================

"""
C++ sanitizer 模块单元测试。

覆盖 sanitize_string_literal、sanitize_uproperty_marks、
sanitize_category 三个函数。
sanitize_identifier 测试已移至 tests/cpp/test_cpp_sanitizer.py。
"""

import pytest
from uasset_read.cpp_gen.sanitizer import (
    sanitize_string_literal,
    sanitize_uproperty_marks,
    sanitize_category,
)
from uasset_read.cpp_gen.math_simplifier import MathSimplifier


# ============================================================================
# sanitize_string_literal 测试
# ============================================================================


class TestSanitizeStringLiteral:
    """sanitize_string_literal 函数测试。"""

    def test_plain_string(self):
        """普通字符串不变。"""
        assert sanitize_string_literal("Hello World") == "Hello World"

    def test_escape_backslash(self):
        """反斜杠转义。"""
        assert sanitize_string_literal("C:\\path") == "C:\\\\path"

    def test_escape_double_quote(self):
        """双引号转义。"""
        assert sanitize_string_literal('Hello "World"') == 'Hello \\"World\\"'

    def test_escape_newline(self):
        """换行符转义。"""
        assert sanitize_string_literal("line1\nline2") == "line1\\nline2"

    def test_escape_carriage_return(self):
        """回车符转义。"""
        assert sanitize_string_literal("cr\rhere") == "cr\\rhere"

    def test_escape_tab(self):
        """制表符转义。"""
        assert sanitize_string_literal("tab\there") == "tab\\there"

    def test_none_returns_empty(self):
        """None 返回空字符串。"""
        assert sanitize_string_literal(None) == ""

    def test_empty_string(self):
        """空字符串不变。"""
        assert sanitize_string_literal("") == ""

    def test_combined_escapes(self):
        """混合转义场景。"""
        assert sanitize_string_literal('path\\to"file"') == 'path\\\\to\\"file\\"'

    def test_backslash_before_quote(self):
        """反斜杠在引号前——反斜杠先转义。"""
        # 输入: a\"b → a\\\"b
        assert sanitize_string_literal('a\\"b') == 'a\\\\\\"b'


# ============================================================================
# sanitize_uproperty_marks 测试
# ============================================================================


class TestSanitizeUpropertyMarks:
    """sanitize_uproperty_marks 函数测试。"""

    def test_valid_marks(self):
        """合法 specifier 保留。"""
        result = sanitize_uproperty_marks(["EditAnywhere", "BlueprintReadWrite"])
        assert result == ["EditAnywhere", "BlueprintReadWrite"]

    def test_filters_invalid_marks(self):
        """非法 specifier 被过滤。"""
        result = sanitize_uproperty_marks(["EditAnywhere", "INJECTED_CODE", "Transient"])
        assert result == ["EditAnywhere", "Transient"]

    def test_none_returns_empty(self):
        """None 返回空列表。"""
        assert sanitize_uproperty_marks(None) == []

    def test_empty_list(self):
        """空列表返回空列表。"""
        assert sanitize_uproperty_marks([]) == []

    def test_deduplication(self):
        """重复 specifier 去重。"""
        result = sanitize_uproperty_marks(["EditAnywhere", "EditAnywhere"])
        assert result == ["EditAnywhere"]

    def test_all_whitelist_specifiers(self):
        """白名单中所有 specifier 都通过。"""
        marks = [
            "EditAnywhere", "EditInstanceOnly", "EditDefaultsOnly",
            "VisibleAnywhere", "VisibleInstanceOnly", "VisibleDefaultsOnly",
            "BlueprintReadWrite", "BlueprintReadOnly", "BlueprintCallable",
            "BlueprintAssignable", "BlueprintPure", "BlueprintType",
            "Transient", "Config", "SaveGame", "Replicated",
            "DuplicateTransient", "Instanced", "NoClear", "Interp",
            "ExposeOnSpawn", "AllowPrivateAccess", "Deprecated",
            "AdvancedDisplay", "Protected",
        ]
        result = sanitize_uproperty_marks(marks)
        assert result == marks

    def test_empty_string_mark(self):
        """空字符串标记被过滤。"""
        assert sanitize_uproperty_marks(["", "EditAnywhere"]) == ["EditAnywhere"]

    def test_non_string_mark(self):
        """非字符串标记被过滤。"""
        assert sanitize_uproperty_marks([123, "EditAnywhere"]) == ["EditAnywhere"]

    def test_case_sensitive(self):
        """大小写敏感——小写变体不通过。"""
        assert sanitize_uproperty_marks(["editanywhere"]) == []
        assert sanitize_uproperty_marks(["EDITANYWHERE"]) == []


# ============================================================================
# sanitize_category 测试
# ============================================================================


class TestSanitizeCategory:
    """sanitize_category 函数测试。"""

    def test_valid_category(self):
        """合法 Category 不变。"""
        assert sanitize_category("My Category") == "My Category"

    def test_remove_double_quotes(self):
        """移除双引号。"""
        assert sanitize_category('My "Category"') == "My Category"

    def test_remove_single_quotes(self):
        """移除单引号。"""
        assert sanitize_category("My 'Category'") == "My Category"

    def test_remove_backslash(self):
        """移除反斜杠。"""
        assert sanitize_category("C:\\path/to") == "Cpathto"

    def test_remove_newline(self):
        """移除换行符。"""
        assert sanitize_category("line\nbreak") == "linebreak"

    def test_remove_carriage_return(self):
        """移除回车符。"""
        assert sanitize_category("line\rbreak") == "linebreak"

    def test_tab_to_space(self):
        """制表符转空格。"""
        assert sanitize_category("my\tcategory") == "my category"

    def test_empty_returns_empty(self):
        """空字符串返回空。"""
        assert sanitize_category("") == ""

    def test_none_returns_empty(self):
        """None 返回空字符串。"""
        assert sanitize_category(None) == ""

    def test_trim_whitespace(self):
        """去除首尾空格。"""
        assert sanitize_category("  Trimmed  ") == "Trimmed"

    def test_compress_spaces(self):
        """压缩连续空格。"""
        assert sanitize_category("My  Big  Category") == "My Big Category"

    def test_preserve_underscore(self):
        """保留下划线。"""
        assert sanitize_category("Valid_Category 123") == "Valid_Category 123"

    def test_remove_special_chars(self):
        """移除特殊字符。"""
        assert sanitize_category("My!@#$%Category") == "MyCategory"

    def test_injection_attempt(self):
        """注入攻击被清除。"""
        assert sanitize_category('"); // INJECTED') == "INJECTED"

    def test_null_bytes(self):
        """null 字节被移除。"""
        assert sanitize_category("abc\0def") == "abcdef"


# ============================================================================
# MathSimplifier 测试（合并自 test_math_simplifier.py）
# ============================================================================


class TestMathSimplifier:
    """蓝图数学函数简化器单元测试。"""

    def test_add_int_simplification(self):
        """测试 Int 加法简化"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("Add_IntInt")
        assert result == "+"

    def test_multiply_float_simplification(self):
        """测试 Float 乘法简化"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("Multiply_FloatFloat")
        assert result == "*"

    def test_boolean_and_simplification(self):
        """测试布尔与简化"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("BooleanAND")
        assert result == "&&"

    def test_is_math_library_function(self):
        """测试判断是否为数学库函数"""
        simplifier = MathSimplifier()
        assert simplifier.is_math_library_function("Add_IntInt") is True
        assert simplifier.is_math_library_function("UnknownFunction") is False

    def test_get_operator_info(self):
        """测试获取运算符信息"""
        simplifier = MathSimplifier()
        info = simplifier.get_operator_info("Add_IntInt")
        assert info["type"] == "arithmetic"
        assert info["operator"] == "+"

    def test_simplify_unknown_function(self):
        """测试简化未知函数返回 None"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("UnknownFunction")
        assert result is None

    def test_simplify_without_type_suffix(self):
        """测试不带类型后缀的简化"""
        simplifier = MathSimplifier()
        # 测试直接匹配（不带类型后缀的函数）
        result = simplifier.simplify("Sin")
        assert result == "FMath::Sin"

    def test_get_operator_info_unknown(self):
        """测试获取未知函数的运算符信息返回 None"""
        simplifier = MathSimplifier()
        info = simplifier.get_operator_info("UnknownFunction")
        assert info is None

    def test_comparison_operator(self):
        """测试比较运算符"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("Greater_FloatFloat")
        assert result == ">"
        info = simplifier.get_operator_info("Greater_FloatFloat")
        assert info["type"] == "comparison"

    def test_logical_operator(self):
        """测试逻辑运算符"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("BooleanOR")
        assert result == "||"
        info = simplifier.get_operator_info("BooleanOR")
        assert info["type"] == "logical"

    def test_math_function(self):
        """测试数学函数保持函数形式"""
        simplifier = MathSimplifier()
        result = simplifier.simplify("Sqrt")
        assert result == "FMath::Sqrt"
        info = simplifier.get_operator_info("Sqrt")
        assert info["type"] == "function"
