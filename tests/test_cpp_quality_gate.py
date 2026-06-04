"""C++ 输出质量门禁 — 验证真实蓝图无致命语法问题。

覆盖 Gap Report P1-1 / P2-1 验收标准：
- 无嵌套函数定义
- 无带空格的标识符
- 无 Python list/dict/dataclass repr
- 无重复 .cpp 标题
"""
from __future__ import annotations

import os
import re

import pytest

from uasset_read.core import parse_single

_REAL_BLUEPRINT = os.path.join(
    os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples"),
    "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)


@pytest.fixture(scope="module")
def cpp_output() -> str:
    """生成真实蓝图的 C++ skeleton 输出。"""
    return parse_single(_REAL_BLUEPRINT, format="cpp_skeleton", tolerant=True)


@pytest.mark.integration
@pytest.mark.quality
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestCppFatalPatterns:
    """验证真实 C++ 输出无致命语法问题。"""

    def test_no_duplicate_cpp_header(self, cpp_output: str):
        """不应出现重复的 .cpp 文件头注释。"""
        count = cpp_output.count("// ABP_FirstPersonCharacter.cpp")
        assert count == 1, f"重复 .cpp 标题: 出现 {count} 次"

    def test_no_nested_function_definitions(self, cpp_output: str):
        """不应出现嵌套函数定义（函数体内包含完整函数签名+花括号）。"""
        # 检查模式：在已有函数体 { } 内部又出现 "void FuncName() {"
        lines = cpp_output.split("\n")
        in_function_body = False
        brace_depth = 0
        for line in lines:
            stripped = line.strip()
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth >= 2:
                # 在第二层花括号内检查是否出现函数签名
                assert not re.match(r'^(void|int|float|bool|auto)\s+\w+\s*\(', stripped), \
                    f"嵌套函数定义: {stripped}"

    def test_no_python_repr_in_output(self, cpp_output: str):
        """不应出现 Python repr（StructValue、列表字面量等）。"""
        assert "StructValue(" not in cpp_output, "Python StructValue repr"
        # 检查 "= [数字" 模式（如 "= [9];"）
        assert not re.search(r'=\s*\[\d', cpp_output), "Python list repr in assignment"

    def test_no_spaces_in_identifiers(self, cpp_output: str):
        """变量声明中不应有带空格的标识符。"""
        # 匹配 "Type Name With Spaces;" 模式（排除注释和字符串）
        for line in cpp_output.split("\n"):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            # 检查变量声明：TYPE NAME;
            m = re.match(r'^(\w[\w:*&]*)\s+([A-Z]\w+(?:\s+\w+)+)\s*[;=]', stripped)
            if m:
                var_name = m.group(2)
                # 排除 UPROPERTY 宏参数和函数签名中的参数
                if "(" not in stripped and "UPROPERTY" not in stripped:
                    pytest.fail(f"带空格的标识符: '{var_name}' in '{stripped}'")

    def test_constructor_uses_super_not_super_class(self, cpp_output: str):
        """构造函数应使用 Super() 而非 Super::ClassName()。"""
        assert "Super::ABP_FirstPersonCharacter()" not in cpp_output, \
            "构造函数应使用 Super() 而非 Super::ClassName()"
        assert ": Super()" in cpp_output, "构造函数缺少 Super() 初始化"

    def test_no_empty_braces_functions(self, cpp_output: str):
        """函数体不应为空（仅有 return; 除外）。"""
        # 匹配 "void Func() {\n}" 或 "void Func() {\n    \n}"
        assert not re.search(r'\{\s*\}', cpp_output), "空函数体 {}"

    def test_output_contains_class_name(self, cpp_output: str):
        """输出应包含正确的类名。"""
        assert "ABP_FirstPersonCharacter" in cpp_output

    def test_output_contains_constructor(self, cpp_output: str):
        """输出应包含构造函数。"""
        assert "ABP_FirstPersonCharacter::ABP_FirstPersonCharacter()" in cpp_output

    def test_component_creation_in_constructor(self, cpp_output: str):
        """构造函数应包含组件创建代码。"""
        assert "CreateDefaultSubobject" in cpp_output


@pytest.mark.integration
@pytest.mark.quality
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestCppParameterBinding:
    """验证蓝图参数数据流绑定到函数参数。"""

    def test_aim_binds_yaw_parameter(self, cpp_output: str):
        """Aim() 应使用 Yaw 参数而非未定义的 Val。"""
        assert "AddControllerYawInput(Yaw)" in cpp_output
        assert "AddControllerYawInput(Val)" not in cpp_output

    def test_aim_binds_pitch_parameter(self, cpp_output: str):
        """Aim() 应使用 Pitch 参数而非未定义的 Val。"""
        assert "AddControllerPitchInput(Pitch)" in cpp_output
        assert "AddControllerPitchInput(Val)" not in cpp_output

    def test_move_resolves_pure_function_sources(self, cpp_output: str):
        """Move() 应解析 Pure 函数输出作为数据源。"""
        # GetActorRightVector / GetActorForwardVector 应被解析
        assert "GetActorRightVector()" in cpp_output or "GetActorForwardVector()" in cpp_output

    def test_move_no_undefined_pin_names(self, cpp_output: str):
        """Move() 不应包含未定义的原始 pin 名。"""
        # WorldDirection, ScaleValue, bForce 是 pin 名，不应直接出现
        move_section = _extract_function_body(cpp_output, "Move")
        assert "WorldDirection" not in move_section
        assert "ScaleValue" not in move_section
        assert "bForce" not in move_section

    def test_move_has_default_value_false(self, cpp_output: str):
        """Move() 的 bForce 参数应解析为默认值 false。"""
        move_section = _extract_function_body(cpp_output, "Move")
        assert "false" in move_section


def _extract_function_body(cpp_output: str, func_name: str) -> str:
    """提取指定函数的函数体内容。"""
    import re
    pattern = rf'void\s+\w+::{func_name}\s*\([^)]*\)\s*\{{(.*?)\}}'
    m = re.search(pattern, cpp_output, re.DOTALL)
    return m.group(1) if m else ""
