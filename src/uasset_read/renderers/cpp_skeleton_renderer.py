"""C++ 骨架独立管线 — 直接使用 LinkerParseResult 生成 C++ 类骨架。

cpp_skeleton 不走标准渲染器管线（IRenderer + RenderOptions），
而是直接接收 LinkerParseResult，通过 cpp_gen 模块生成完整的 .h/.cpp 输出。

输出结构：
    1. // {ClassName}.h 头文件（声明 + UPROPERTY + 方法签名）
    2. // {ClassName}.cpp 实现文件（构造函数 + 方法函数体）
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR

logger = logging.getLogger(__name__)

# UE 属性类型到 C++ 类型映射（回退模式使用）
_UE_TO_CPP_TYPE = {
    "IntProperty": "int32",
    "Int64Property": "int64",
    "FloatProperty": "float",
    "DoubleProperty": "double",
    "BoolProperty": "bool",
    "StrProperty": "FString",
    "NameProperty": "FName",
    "TextProperty": "FText",
    "ObjectProperty": "UObject*",
    "ClassProperty": "UClass*",
    "SoftObjectProperty": "TSoftObjectPtr<UObject>",
    "SoftClassProperty": "TSoftClassPtr<UObject>",
    "ArrayProperty": "TArray",
    "MapProperty": "TMap",
    "SetProperty": "TSet",
    "StructProperty": "FStruct",
    "VectorProperty": "FVector",
    "Vector2DProperty": "FVector2D",
    "Vector4Property": "FVector4",
    "RotatorProperty": "FRotator",
    "TransformProperty": "FTransform",
    "LinearColorProperty": "FLinearColor",
    "ByteProperty": "uint8",
    "EnumProperty": "uint8",
}


class CppSkeletonRenderer:
    """C++ 骨架独立管线 — 直接消费 LinkerParseResult，输出 .h 声明和 .cpp 实现。

    注意：该类不再继承 IRenderer，也不注册到 RENDERER_REGISTRY。
    core.parse_single 在标准渲染器分发之前拦截 format=="cpp_skeleton"，
    直接实例化此类并调用 generate(result)。

    保留旧类名 CppSkeletonRenderer 仅为向后兼容导入（测试文件使用）。
    """

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def generate(self, result) -> str:
        """使用 cpp_gen 管线从 LinkerParseResult 生成完整 C++ 骨架。

        Args:
            result: LinkerParseResult（parse_uasset_with_linker 的返回值）

        Returns:
            C++ 骨架字符串（.h 声明 + .cpp 实现）
        """
        from uasset_read.cpp_gen import extract_cpp_class_skeleton
        from uasset_read.cpp_gen.formatters import (
            format_cpp_header,
            format_full_cpp_implementation,
            format_cpp_interfaces,
            format_cpp_enums,
            format_cpp_structs,
            format_cpp_delegates,
            format_cpp_replication,
        )

        try:
            cpp_ir = extract_cpp_class_skeleton(result)
        except (ValueError, AttributeError) as exc:
            logger.warning("extract_cpp_class_skeleton 失败: %s", exc)
            return f"// C++ 骨架提取失败: {exc}\n"

        sections: list[str] = []

        # 对称语义输出：接口、枚举、结构体、委托（放在类定义之前）
        blueprint = getattr(result, 'blueprint', None)
        if blueprint:
            # 接口
            interfaces_text = format_cpp_interfaces(getattr(blueprint, 'interfaces', []))
            if interfaces_text.strip():
                sections.append(interfaces_text)

            # 枚举
            enums_text = format_cpp_enums(getattr(blueprint, 'enums', []))
            if enums_text.strip():
                sections.append(enums_text)

            # 结构体
            structs_text = format_cpp_structs(getattr(blueprint, 'structs', []))
            if structs_text.strip():
                sections.append(structs_text)

            # 委托
            delegates_text = format_cpp_delegates(getattr(blueprint, 'delegates', []))
            if delegates_text.strip():
                sections.append(delegates_text)

        # .h 头文件
        header_text = format_cpp_header(cpp_ir)
        sections.append(f"// {cpp_ir.name}.h")
        sections.append(header_text)

        # 对称语义输出：复制（放在类声明之后）
        if blueprint:
            replication_text = format_cpp_replication(getattr(blueprint, 'replication', None))
            if replication_text.strip():
                sections.append(replication_text)

        # .cpp 实现文件（含函数体 + 构造函数）
        # format_full_cpp_implementation() 内部已输出 .cpp 标题，不再重复
        impl_text = format_full_cpp_implementation(cpp_ir)
        if impl_text.strip():
            sections.append(impl_text)

            # 构造函数追加到 .cpp 实现部分
            ctor_text = cpp_ir.constructor.get("constructor_text", "")
            if ctor_text and ctor_text.strip():
                sections.append(ctor_text)

        return "\n".join(sections)

    def generate_fallback(self, ir: "PackageIR") -> str:
        """回退路径：从 PackageIR 生成简单的 .h 头文件（无函数体）。

        仅在 LinkerParseResult 不可用时使用（例如仅构建了 IR 的场景）。
        """
        return self._render_simple_header(ir)

    # 向后兼容：旧 render(ir, options) 接口转发到 fallback
    def render(self, ir: "PackageIR", options) -> str:
        """保留旧 render 签名以兼容历史调用（转发到 generate_fallback）。"""
        logger.warning(
            "CppSkeletonRenderer.render(ir, options) 已废弃，"
            "请使用 generate(result) 走独立管线"
        )
        return self.generate_fallback(ir)

    def _render_simple_header(self, ir: PackageIR) -> str:
        """从 PackageIR 生成简单的 .h 头文件（无函数体，回退模式）。"""
        lines: list[str] = []

        # 对称语义输出：接口、枚举、结构体、委托（放在类定义之前）
        if ir.blueprint:
            # 接口
            if ir.blueprint.interfaces:
                lines.append("// Blueprint Interfaces")
                for iface in ir.blueprint.interfaces:
                    cpp_name = iface.cpp_type or iface.name
                    if not cpp_name:
                        continue
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

            # 枚举
            if ir.blueprint.enums:
                lines.append("// Blueprint Enums")
                for enum in ir.blueprint.enums:
                    cpp_name = enum.cpp_type or enum.name
                    if not cpp_name:
                        continue
                    lines.append(f"UENUM(BlueprintType)")
                    lines.append(f"enum class {cpp_name} : uint8")
                    lines.append("{")
                    if enum.values:
                        for i, val in enumerate(enum.values):
                            comma = "," if i < len(enum.values) - 1 else ""
                            if val.value is not None:
                                lines.append(f"    {val.name} = {val.value}{comma}")
                            else:
                                lines.append(f"    {val.name}{comma}")
                    else:
                        lines.append("    UMETA(DisplayName = \"Default\")")
                    lines.append("};")
                    lines.append("")

            # 结构体
            if ir.blueprint.structs:
                lines.append("// Blueprint Structs")
                for struct in ir.blueprint.structs:
                    cpp_name = struct.cpp_type or struct.name
                    if not cpp_name:
                        continue
                    lines.append(f"USTRUCT(BlueprintType)")
                    lines.append(f"struct {cpp_name}")
                    lines.append("{")
                    lines.append("    GENERATED_BODY()")
                    lines.append("")
                    if struct.fields:
                        for field_item in struct.fields:
                            if field_item.cpp_type and field_item.name:
                                lines.append(f"    UPROPERTY(BlueprintReadWrite, EditAnywhere)")
                                field_decl = f"    {field_item.cpp_type} {field_item.name}"
                                if field_item.default_value:
                                    field_decl += f" = {field_item.default_value}"
                                field_decl += ";"
                                lines.append(field_decl)
                                lines.append("")
                    else:
                        lines.append("    // Add fields here")
                        lines.append("")
                    lines.append("};")
                    lines.append("")

            # 委托
            if ir.blueprint.delegates:
                lines.append("// Blueprint Delegates")
                for delegate in ir.blueprint.delegates:
                    cpp_name = delegate.cpp_type or delegate.name
                    if not cpp_name:
                        continue
                    if delegate.is_multicast:
                        lines.append(f"DECLARE_DYNAMIC_MULTICAST_DELEGATE({cpp_name});")
                    else:
                        lines.append(f"DECLARE_DYNAMIC_DELEGATE({cpp_name});")
                lines.append("")

        # 从包名提取类名
        class_name = ir.header.package_name.split("/")[-1]
        class_name = class_name.replace("_C", "") if class_name.endswith("_C") else class_name

        # 确定父类
        parent_class = None
        for export in ir.exports:
            if export.parent_class:
                parent_class = export.parent_class
                break
        if parent_class is None:
            parent_class = ir.header.package_class.replace("_C", "")
        parent_cpp = self._ue_to_cpp_class(parent_class)

        # 头文件保护 + 包含
        lines.append("#pragma once")
        lines.append("")
        lines.append('#include "CoreMinimal.h"')

        # 收集所有需要的类型头文件
        cpp_types: set[str] = set()
        for export in ir.exports:
            for prop in export.properties:
                cpp_type = self._property_to_cpp_type(prop.type, prop.value)
                base_type = cpp_type.split("<")[0].rstrip("*")
                if base_type.startswith("F") or base_type.startswith("T"):
                    cpp_types.add(base_type)

        for export in ir.exports:
            if export.parent_class:
                parent_base = parent_cpp.rstrip("*")
                if parent_base.startswith("F") or parent_base.startswith("T"):
                    cpp_types.add(parent_base)

        # 移除 CoreMinimal — 已在上方手动 #include，避免重复
        cpp_types.discard("CoreMinimal")

        for cpp_type in sorted(cpp_types):
            lines.append(f'#include "{cpp_type}.h"')
        lines.append("")

        # generated.h 必须最后包含
        lines.append(f'#include "{class_name}.generated.h"')
        lines.append("")

        # 类声明
        lines.append("UCLASS()")
        lines.append(f"class {class_name} : public {parent_cpp}")
        lines.append("{")
        lines.append("\tGENERATED_BODY()")
        lines.append("")
        lines.append("public:")
        lines.append("")

        # 属性
        properties_added = False
        for export in ir.exports:
            for prop in export.properties:
                if not properties_added:
                    lines.append("\t// Properties")
                    properties_added = True
                cpp_type = self._property_to_cpp_type(prop.type, prop.value)
                default = self._format_cpp_default(prop.value)
                if default:
                    lines.append(f"\tUPROPERTY()")
                    lines.append(f"\t{cpp_type} {prop.name} = {default};")
                else:
                    lines.append(f"\tUPROPERTY()")
                    lines.append(f"\t{cpp_type} {prop.name};")

        if not properties_added:
            lines.append("\t// (No properties found)")

        lines.append("};")
        lines.append("")

        # 对称语义输出：复制（放在类声明之后）
        if ir.blueprint and ir.blueprint.replication:
            replication = ir.blueprint.replication
            if replication.replicated_vars or replication.on_rep_functions:
                lines.append("// Replication")
                lines.append("")
                lines.append("virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;")
                lines.append("")
                if replication.replicated_vars:
                    lines.append("// Replicated Properties:")
                    for var in replication.replicated_vars:
                        comment = f"// DOREPLIFETIME({var.name})"
                        if var.on_rep_function:
                            comment += f" with OnRep: {var.on_rep_function}"
                        lines.append(comment)
                    lines.append("")
                for on_rep_func in replication.on_rep_functions:
                    lines.append(f"UFUNCTION()")
                    lines.append(f"void {on_rep_func}();")
                    lines.append("")

        return "\n".join(lines)

    def _ue_to_cpp_class(self, ue_class: str) -> str:
        """将 UE 类名转换为 C++ 类名。"""
        base = ue_class.split("/")[-1] if "/" in ue_class else ue_class
        if base.startswith(("A", "U", "E", "F", "T")):
            return base
        return f"U{base}"

    def _property_to_cpp_type(self, prop_type: str, value: Any) -> str:
        """将 UE 属性类型映射为 C++ 类型。"""
        if prop_type in _UE_TO_CPP_TYPE:
            cpp_type = _UE_TO_CPP_TYPE[prop_type]
        else:
            cpp_type = "UObject*"

        # 数组类型需要模板参数
        if prop_type == "ArrayProperty":
            if isinstance(value, list) and len(value) > 0:
                elem_type = type(value[0]).__name__
                cpp_type = f"TArray<{elem_type}>"
            else:
                cpp_type = "TArray<UObject*>"

        return cpp_type

    def _format_cpp_default(self, value) -> str:
        """格式化 C++ 默认值。"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return f"{value}f"
        if isinstance(value, str):
            return f'TEXT("{value}")'
        return ""
