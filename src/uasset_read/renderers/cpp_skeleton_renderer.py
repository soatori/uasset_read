"""C++ 头文件骨架渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR

# UE 属性类型到 C++ 类型映射
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

# 集合类型，需要包含模板参数
_CONTAINER_TYPES = {"ArrayProperty", "MapProperty", "SetProperty"}


class CppSkeletonRenderer(IRenderer):
    """C++ 类骨架生成器（.h header）。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
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
        base_type = prop_type
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

    def _format_cpp_default(self, value: Any) -> str:
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
            return f"TEXT(\"{value}\")"
        return ""

    @property
    def format_name(self) -> str:
        return "cpp_skeleton"


register_renderer("cpp_skeleton", CppSkeletonRenderer)
