"""
C++ 头文件格式化模块 — CppClassIR → UE 标准 .h 文本。

Per D-05: 完整 UE 头文件模板从 JSON IR。
Per T-056-05: 转义字符串值中的注释。
Per T-056-06: 验证类名匹配 UE 命名约定。

导出：
    format_cpp_header: CppClassIR → .h 文本转换函数
"""
from __future__ import annotations

import html
import logging
import re
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.cpp_gen.formatters import CppCallStatement

from uasset_read.cpp_gen.formatters import CppClassIR, CppProperty, CppHeaderMeta, CppMethodIR, CppCallStatement

logger = logging.getLogger(__name__)


# ============================================================================
# 安全相关常量（T-056-05, T-056-06）
# ============================================================================

# UE 类名允许的模式：字母数字和下划线，以字母或下划线开头
UE_CLASS_NAME_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


# ============================================================================
# 核心格式化函数
# ============================================================================

def format_cpp_header(ir: CppClassIR) -> str:
    """将 CppClassIR 转换为标准 UE .h 头文件文本。

    Per D-05: 输出格式包含：
    1. #pragma once（如果 header_meta.pragma_once）
    2. #include "CoreMinimal.h"（始终添加）
    3. header_meta.includes 的 #include 行（排序）
    4. header_meta.generated_include 的 #include（始终最后）
    5. UCLASS() 宏
    6. class 声明和继承
    7. GENERATED_BODY()
    8. public: 构造函数声明
    9. protected: 属性声明

    Args:
        ir: CppClassIR 数据模型

    Returns:
        标准 UE .h 头文件文本
    """
    # T-056-06: 验证并清理类名
    class_name = _sanitize_class_name(ir.name)
    parent_class = _sanitize_class_name(ir.parent_class)

    # 构建输出行
    lines: List[str] = []

    # 1. #pragma once
    if ir.header_meta.pragma_once:
        lines.append("#pragma once")

    # 2. 空行
    lines.append("")

    # 3. #include "CoreMinimal.h"（UE 约定，始终添加）
    lines.append('#include "CoreMinimal.h"')

    # 4. header_meta.includes（去重 + 排序）
    includes = sorted(set(ir.header_meta.includes))
    for inc in includes:
        lines.append(f'#include {inc}')

    # 5. generated_include（始终最后一个 include）
    if ir.header_meta.generated_include:
        generated_inc = _sanitize_generated_include(ir.header_meta.generated_include, class_name)
        lines.append(f'#include {generated_inc}')

    # 6. 空行
    lines.append("")

    # 7. UCLASS 宏（蓝图生成的类默认 Blueprintable）
    lines.append("UCLASS(Blueprintable)")

    # 8. class 声明
    lines.append(f"class {class_name} : public {parent_class}")
    lines.append("{")
    lines.append("    GENERATED_BODY()")

    # 9. 空行
    lines.append("")

    # 10. public: 构造函数声明
    lines.append("public:")
    lines.append(f"    {class_name}();")

    # 11. 空行
    lines.append("")

    # 12. protected: 属性声明
    lines.append("protected:")

    # 分离组件和变量属性（组件优先）
    components = [p for p in ir.properties if p.category == "component"]
    variables = [p for p in ir.properties if p.category != "component"]

    # 组件声明
    if components:
        lines.append("    // Components")
        for prop in components:
            lines.extend(_format_component_property(prop))

    # 变量声明
    if variables:
        if components:
            lines.append("")  # 组件和变量之间空行
        for prop in variables:
            lines.extend(_format_variable_property(prop))

    # 13. 方法声明
    if ir.methods:
        lines.append("")
        lines.append("public:")
        lines.append("    // Blueprint Functions")
        for i, method in enumerate(ir.methods):
            if i > 0:
                lines.append("")
            lines.extend(_format_method_declaration(method))

    # 14. 类结束
    lines.append("};")

    # 14. 尾随换行
    lines.append("")

    return '\n'.join(lines)


# ============================================================================
# 辅助函数
# ============================================================================

def _sanitize_class_name(name: str) -> str:
    """清理类名以匹配 UE 命名约定（T-056-06）。

    只允许字母数字和下划线，以字母或下划线开头。
    非法字符替换为下划线。

    Args:
        name: 原始类名

    Returns:
        清理后的类名
    """
    if not name:
        return "UUnknownClass"

    # 移除非法字符，替换为下划线
    sanitized = re.sub(r'[^A-Za-z0-9_]', '_', name)

    # 确保以字母或下划线开头
    if sanitized and sanitized[0].isdigit():
        sanitized = f"_{sanitized}"

    if not UE_CLASS_NAME_PATTERN.match(sanitized):
        logger.warning(f"Class name '{name}' could not be sanitized, using default")
        return "UUnknownClass"

    return sanitized


def _sanitize_generated_include(include: str, class_name: str) -> str:
    """清理 generated.h 包含路径。

    Args:
        include: 原始包含路径
        class_name: 清理后的类名

    Returns:
        清理后的包含路径（使用清理后的类名）
    """
    # 使用清理后的类名重建 generated_include
    # 格式: "{ClassName}.generated.h"
    return f'"{class_name}.generated.h"'


def _sanitize_comment(comment: str) -> str:
    """清理注释字符串以防止注入（T-056-05）。

    转义 HTML 特殊字符，防止潜在的代码注入。

    Args:
        comment: 原始注释文本

    Returns:
        清理后的注释文本
    """
    if not comment:
        return ""

    # 转义 HTML 特殊字符
    sanitized = html.escape(comment, quote=False)

    # 移除可能导致问题的其他字符
    sanitized = sanitized.replace('\n', ' ')
    sanitized = sanitized.replace('\r', '')

    return sanitized


def _format_component_property(prop: CppProperty) -> List[str]:
    """格式化组件属性声明。

    Per D-04: 组件使用 UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced)
    并添加 Category = "Components" 和 AllowPrivateAccess。

    Args:
        prop: CppProperty（category="component"）

    Returns:
        格式化后的行列表
    """
    lines: List[str] = []

    # 构建完整 UPROPERTY 参数
    marks = prop.uproperty_marks.copy()
    uproperty_args = ", ".join(marks)
    uproperty_args += ', Category = "Components"'
    uproperty_args += ', meta = (AllowPrivateAccess = "true")'

    lines.append(f"    UPROPERTY({uproperty_args})")

    # 属性声明
    decl = f"    {prop.cpp_type} {prop.name};"

    # 添加注释（如果有）
    if prop.cpp_comment:
        sanitized_comment = _sanitize_comment(prop.cpp_comment)
        decl += f" // {sanitized_comment}"

    lines.append(decl)

    return lines


def _format_variable_property(prop: CppProperty) -> List[str]:
    """格式化变量属性声明。

    Per D-04: 变量使用 UPROPERTY 标记列表，添加 Category。
    默认值根据类型格式化。

    Args:
        prop: CppProperty（category != "component"）

    Returns:
        格式化后的行列表
    """
    lines: List[str] = []

    # 构建完整 UPROPERTY 参数
    marks = prop.uproperty_marks.copy()
    uproperty_args = ", ".join(marks)

    # 添加 Category（如果有）
    if prop.category:
        uproperty_args += f', Category = "{prop.category}"'

    lines.append(f"    UPROPERTY({uproperty_args})")

    # 属性声明
    decl = f"    {prop.cpp_type} {prop.name}"

    # 添加默认值（如果有且非空）
    if prop.default_value is not None:
        default_str = _format_default_value(prop.cpp_type, prop.default_value)
        if default_str:
            decl += f" = {default_str}"

    decl += ";"

    # 添加注释（如果有）
    if prop.cpp_comment:
        sanitized_comment = _sanitize_comment(prop.cpp_comment)
        decl += f" // {sanitized_comment}"

    lines.append(decl)

    return lines


def _format_default_value(cpp_type: str, value: any) -> str:
    """格式化默认值字符串。

    Args:
        cpp_type: C++ 类型名
        value: 默认值

    Returns:
        格式化后的默认值字符串
    """
    if value is None:
        return ""

    # 空字符串或纯空白 — 无有效默认值
    if isinstance(value, str) and not value.strip():
        return ""

    # 处理布尔值
    if cpp_type == "bool":
        return "true" if value else "false"

    # 处理浮点类型（添加 f 后缀）
    if cpp_type in ("float", "double"):
        return f"{float(value)}f"

    # 处理整数类型（无后缀）
    if cpp_type in ("int", "int32", "int64", "uint8", "uint16", "uint32", "uint64", "byte"):
        return str(int(value))

    # 处理字符串类型（TEXT 包装）
    if cpp_type in ("FString", "FName"):
        return f'TEXT("{value}")'

    # FText 太复杂，跳过（当前不支持）
    if cpp_type == "FText":
        return "FText::GetEmpty()"

    # 其他类型直接返回
    return str(value)


def _format_method_declaration(method: CppMethodIR) -> List[str]:
    """将 CppMethodIR 渲染为 .h 声明行列表。

    改进：支持 is_static、is_virtual、is_pure 等新字段。

    Examples:
        Move → ["    UFUNCTION(BlueprintCallable)", "    void Move(double LeftRight, double ForwardBackward);"]
        PrimaryThumbstick → ["    void PrimaryThumbstick(double Axis_X, double Axis_Y) override;"]
        Aim → ["    UFUNCTION(BlueprintPure)", "    static float GetAimAngle();"]
    """
    lines: List[str] = []

    # UFUNCTION 宏
    if method.ufunction_specifiers:
        spec_str = ", ".join(method.ufunction_specifiers)
        lines.append(f"    UFUNCTION({spec_str})")

    # 参数列表
    param_str = ", ".join(f"{p.cpp_type} {p.name}" for p in method.parameters)

    # 修饰符
    modifiers = []
    if method.is_static:
        modifiers.append("static")
    if method.is_virtual and not method.is_override:
        modifiers.append("virtual")
    if method.is_const:
        modifiers.append("const")
    if method.is_override:
        modifiers.append("override")

    # 构建声明
    decl = f"    {method.return_type} {method.cpp_name}({param_str})"

    if modifiers:
        decl += " " + " ".join(modifiers)

    decl += ";"
    lines.append(decl)

    return lines


def format_cpp_call_statements(statements: List["CppCallStatement"]) -> str:
    """将 CppCallStatement 列表渲染为 .cpp 参考文本。

    Examples:
        CppCallStatement(method_name="Jump", target="this", args=[]) → "this->Jump();"
    """
    if not statements:
        return ""

    lines = ["// Call Reference"]
    for stmt in statements:
        op = "->"  # UE 指针访问符
        args_str = ", ".join(stmt.args)
        lines.append(f"{stmt.target}{op}{stmt.method_name}({args_str});")

    return "\n".join(lines) + "\n"


# ============================================================================
# 对称语义输出：接口、枚举、结构体、委托、复制
# ============================================================================

def format_cpp_interfaces(interfaces: list) -> str:
    """将接口 IR 列表格式化为 C++ UINTERFACE 声明。

    Args:
        interfaces: InterfaceIR 列表

    Returns:
        C++ 接口声明文本
    """
    if not interfaces:
        return ""

    lines = ["// Blueprint Interfaces"]
    for iface in interfaces:
        cpp_name = getattr(iface, 'cpp_type', '') or getattr(iface, 'name', '')
        if not cpp_name:
            continue

        # UINTERFACE 声明
        lines.append(f"UINTERFACE(Blueprintable)")
        lines.append(f"class {cpp_name} : public UInterface")
        lines.append("{")
        lines.append("    GENERATED_BODY()")
        lines.append("};")
        lines.append("")

        # 对应的 I 前缀类
        i_name = cpp_name if cpp_name.startswith('I') else f"I{cpp_name}"
        lines.append(f"class {i_name}")
        lines.append("{")
        lines.append("    GENERATED_BODY()")
        lines.append("")
        lines.append("public:")
        lines.append("    // Add interface functions here")
        lines.append("};")
        lines.append("")

    return "\n".join(lines)


def format_cpp_enums(enums: list) -> str:
    """将枚举 IR 列表格式化为 C++ UENUM enum class 声明。

    Args:
        enums: EnumIR 列表

    Returns:
        C++ 枚举声明文本
    """
    if not enums:
        return ""

    lines = ["// Blueprint Enums"]
    for enum in enums:
        cpp_name = getattr(enum, 'cpp_type', '') or getattr(enum, 'name', '')
        if not cpp_name:
            continue

        lines.append(f"UENUM(BlueprintType)")
        lines.append(f"enum class {cpp_name} : uint8")
        lines.append("{")

        values = getattr(enum, 'values', [])
        if values:
            for i, val in enumerate(values):
                val_name = getattr(val, 'name', '')
                val_value = getattr(val, 'value', None)
                comma = "," if i < len(values) - 1 else ""
                if val_value is not None:
                    lines.append(f"    {val_name} = {val_value}{comma}")
                else:
                    lines.append(f"    {val_name}{comma}")
        else:
            lines.append("    UMETA(DisplayName = \"Default\")")

        lines.append("};")
        lines.append("")

    return "\n".join(lines)


def format_cpp_structs(structs: list) -> str:
    """将结构体 IR 列表格式化为 C++ USTRUCT 声明。

    Args:
        structs: StructIR 列表

    Returns:
        C++ 结构体声明文本
    """
    if not structs:
        return ""

    lines = ["// Blueprint Structs"]
    for struct in structs:
        cpp_name = getattr(struct, 'cpp_type', '') or getattr(struct, 'name', '')
        if not cpp_name:
            continue

        lines.append(f"USTRUCT(BlueprintType)")
        lines.append(f"struct {cpp_name}")
        lines.append("{")
        lines.append("    GENERATED_BODY()")
        lines.append("")

        fields = getattr(struct, 'fields', [])
        if fields:
            for field_item in fields:
                field_name = getattr(field_item, 'name', '')
                field_type = getattr(field_item, 'cpp_type', '')
                default_val = getattr(field_item, 'default_value', '')

                if field_type and field_name:
                    decl = f"    UPROPERTY(BlueprintReadWrite, EditAnywhere)"
                    lines.append(decl)
                    field_decl = f"    {field_type} {field_name}"
                    if default_val:
                        field_decl += f" = {default_val}"
                    field_decl += ";"
                    lines.append(field_decl)
                    lines.append("")
        else:
            lines.append("    // Add fields here")
            lines.append("")

        lines.append("};")
        lines.append("")

    return "\n".join(lines)


def format_cpp_delegates(delegates: list) -> str:
    """将委托 IR 列表格式化为 C++ DECLARE_DYNAMIC_DELEGATE 宏。

    Args:
        delegates: DelegateIR 列表

    Returns:
        C++ 委托声明文本
    """
    if not delegates:
        return ""

    lines = ["// Blueprint Delegates"]
    for delegate in delegates:
        cpp_name = getattr(delegate, 'cpp_type', '') or getattr(delegate, 'name', '')
        if not cpp_name:
            continue

        is_multicast = getattr(delegate, 'is_multicast', False)
        signature = getattr(delegate, 'signature', '')

        if is_multicast:
            lines.append(f"DECLARE_DYNAMIC_MULTICAST_DELEGATE({cpp_name});")
        else:
            # 解析签名提取返回类型和参数
            return_type, params = _parse_delegate_signature(signature)
            param_count = len(params)

            # 根据参数数量选择宏
            macro_suffix = ""
            if param_count > 0:
                macro_suffix = f"_{param_count}"

            macro_name = f"DECLARE_DYNAMIC_DELEGATE{macro_suffix}"
            param_str = ", ".join([f"{p[0]} {p[1]}" for p in params]) if params else ""

            if param_str:
                lines.append(f"{macro_name}({cpp_name}, {return_type}, {param_str});")
            else:
                lines.append(f"{macro_name}({cpp_name}, {return_type});")

    return "\n".join(lines)


def format_cpp_replication(replication) -> str:
    """将复制 IR 格式化为 C++ GetLifetimeReplicatedProps 实现。

    Args:
        replication: ReplicationIR 实例

    Returns:
        C++ 复制实现文本
    """
    if not replication:
        return ""

    replicated_vars = getattr(replication, 'replicated_vars', [])
    on_rep_functions = getattr(replication, 'on_rep_functions', [])

    if not replicated_vars and not on_rep_functions:
        return ""

    lines = ["// Replication"]
    lines.append("")

    # GetLifetimeReplicatedProps 声明
    lines.append("virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;")
    lines.append("")

    # 复制变量声明（带 DOREPLIFETIME 注释）
    if replicated_vars:
        lines.append("// Replicated Properties:")
        for var in replicated_vars:
            var_name = getattr(var, 'name', '')
            cpp_type = getattr(var, 'cpp_type', '')
            on_rep = getattr(var, 'on_rep_function', '')

            if var_name:
                comment = f"// DOREPLIFETIME({var_name})"
                if on_rep:
                    comment += f" with OnRep: {on_rep}"
                lines.append(comment)
        lines.append("")

    # OnRep 函数声明
    for on_rep_func in on_rep_functions:
        lines.append(f"UFUNCTION()")
        lines.append(f"void {on_rep_func}();")
        lines.append("")

    return "\n".join(lines)


def _parse_delegate_signature(signature: str) -> tuple:
    """解析委托签名字符串。

    Args:
        signature: 签名字符串（如 "void(int32, float)"）

    Returns:
        (return_type, [(type, name), ...])
    """
    if not signature:
        return ("void", [])

    # 匹配 "ReturnType(param1, param2, ...)"
    import re
    match = re.match(r'(\w+)\((.*)\)', signature)
    if not match:
        return ("void", [])

    return_type = match.group(1)
    params_str = match.group(2).strip()

    if not params_str:
        return (return_type, [])

    params = []
    for i, param in enumerate(params_str.split(',')):
        param = param.strip()
        if param:
            params.append((param, f"Param{i}"))

    return (return_type, params)


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "format_cpp_header",
    "format_cpp_call_statements",
    "format_cpp_interfaces",
    "format_cpp_enums",
    "format_cpp_structs",
    "format_cpp_delegates",
    "format_cpp_replication",
]