"""C++ 骨架渲染器 — 使用 cpp_gen 模块生成完整的 .h 头文件和 .cpp 实现。

输出结构：
    1. // {ClassName}.h 头文件（声明 + UPROPERTY + 方法签名）
    2. // {ClassName}.cpp 实现文件（构造函数 + 方法函数体）
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

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


class CppSkeletonRenderer(IRenderer):
    """C++ 骨架生成器 — 输出 .h 头文件声明和 .cpp 函数体实现。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        """渲染 C++ 骨架输出。

        优先使用 cpp_gen 管线（extract_cpp_class_skeleton → format_cpp_header +
        format_full_cpp_implementation），输出完整的 .h 声明和 .cpp 函数体。
        如果 linker_result 不可用，回退到基于 PackageIR 的简单输出。
        """
        linker_result = options.linker_result
        if linker_result is not None:
            return self._render_from_linker_result(linker_result)

        # 回退：从 PackageIR 生成简单头文件（无函数体）
        logger.warning(
            "linker_result 不可用，回退到简单属性骨架（无函数体）"
        )
        return self._render_simple_header(ir)

    def _render_from_linker_result(self, result) -> str:
        """使用 cpp_gen 管线从 LinkerParseResult 生成完整 C++ 骨架。"""
        from uasset_read.cpp_gen import extract_cpp_class_skeleton
        from uasset_read.cpp_gen.formatters import (
            format_cpp_header,
            format_full_cpp_implementation,
        )

        try:
            cpp_ir = extract_cpp_class_skeleton(result)
        except (ValueError, AttributeError) as exc:
            logger.warning("extract_cpp_class_skeleton 失败: %s", exc)
            return f"// C++ 骨架提取失败: {exc}\n"

        sections: list[str] = []

        # .h 头文件
        header_text = format_cpp_header(cpp_ir)
        sections.append(f"// {cpp_ir.name}.h")
        sections.append(header_text)

        # .cpp 实现文件（含函数体 + 构造函数）
        impl_text = format_full_cpp_implementation(cpp_ir)
        if impl_text.strip():
            sections.append(f"// {cpp_ir.name}.cpp")
            sections.append(impl_text)

            # 构造函数追加到 .cpp 实现部分
            ctor_text = cpp_ir.constructor.get("constructor_text", "")
            if ctor_text and ctor_text.strip():
                sections.append(ctor_text)

        return "\n".join(sections)

    def _render_simple_header(self, ir: PackageIR) -> str:
        """从 PackageIR 生成简单的 .h 头文件（无函数体，回退模式）。"""
        lines: list[str] = []

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

    @property
    def format_name(self) -> str:
        return "cpp_skeleton"


register_renderer("cpp_skeleton", CppSkeletonRenderer)
