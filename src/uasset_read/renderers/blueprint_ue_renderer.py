"""模拟 UE Ctrl+C 文本格式渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR
    from uasset_read.models.properties import StructValue, TextValue, EnumValue


def _escape_ue_value(value: str) -> str:
    """转义 UE 格式字符串中的特殊字符。"""
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_struct_ue(struct_val: "StructValue") -> str:
    """将 StructValue 格式化为 UE 风格：(Field1=Value1,Field2=Value2)。"""
    from uasset_read.models.properties import StructValue

    if not isinstance(struct_val, StructValue):
        return str(struct_val)

    fields = struct_val.fields if hasattr(struct_val, "fields") else {}
    if not fields:
        return "()"

    parts = []
    for k, v in fields.items():
        formatted = _format_ue_value(v)
        parts.append(f"{k}={formatted}")
    return "(" + ",".join(parts) + ")"


def _format_text_ue(text_val: "TextValue") -> str:
    """将 TextValue 格式化为 UE FText 风格。"""
    from uasset_read.models.properties import TextValue

    if not isinstance(text_val, TextValue):
        return str(text_val)

    source = text_val.source_string if hasattr(text_val, "source_string") and text_val.source_string else ""
    key = text_val.key if hasattr(text_val, "key") and text_val.key else ""
    ns = text_val.namespace if hasattr(text_val, "namespace") and text_val.namespace else ""

    # UE Ctrl+C 通常显示为 Inv( Namespace="...", Key="...", SourceString="..." )
    inv_parts = []
    if ns:
        inv_parts.append(f'Namespace="{_escape_ue_value(ns)}"')
    if key:
        inv_parts.append(f'Key="{_escape_ue_value(key)}"')
    if source:
        inv_parts.append(f'SourceString="{_escape_ue_value(source)}"')

    return 'Inv(' + ",".join(inv_parts) + ')' if inv_parts else '""'


def _format_enum_ue(enum_val: "EnumValue") -> str:
    """将 EnumValue 格式化为 UE 风格：EnumType::ValueName。"""
    from uasset_read.models.properties import EnumValue

    if not isinstance(enum_val, EnumValue):
        return str(enum_val)

    enum_type = getattr(enum_val, "enum_type", "") or ""
    value_name = getattr(enum_val, "value_name", "") or ""

    if enum_type and value_name:
        return f"{enum_type}::{value_name}"
    return value_name or enum_type or "None"


def _format_ue_value(value: Any) -> str:
    """格式化值为 UE 风格字符串，处理复杂属性类型。"""
    from uasset_read.models.properties import (
        StructValue, TextValue, EnumValue, MapValue, SetValue, DelegateValue, SoftObjectPathValue
    )

    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _escape_ue_value(value)

    # 高级属性类型
    if isinstance(value, StructValue):
        return _format_struct_ue(value)
    if isinstance(value, TextValue):
        return _format_text_ue(value)
    if isinstance(value, EnumValue):
        return _format_enum_ue(value)
    if isinstance(value, SoftObjectPathValue):
        path = getattr(value, "asset_path", "") or ""
        sub = getattr(value, "sub_path", "") or ""
        full = path
        if sub:
            full = f"{full}.{sub}" if full else sub
        return f'"{_escape_ue_value(full)}"' if full else '""'
    if isinstance(value, (list, tuple)):
        items = [_format_ue_value(item) for item in value]
        return "(" + ",".join(items) + ")"
    if isinstance(value, dict):
        parts = [f"{_escape_ue_value(str(k))}={_format_ue_value(v)}" for k, v in value.items()]
        return "(" + ",".join(parts) + ")"

    # Fallback: 避免 Python repr（ClassName(...) 或 <object at 0x...>）
    # 对未知类型使用安全的字符串表示
    if hasattr(value, '__dict__'):
        # dataclass 或普通对象 → 展开为 Key=Value 对
        parts = [f"{k}={_format_ue_value(v)}" for k, v in value.__dict__.items()]
        return "(" + ",".join(parts) + ")"
    return _escape_ue_value(str(value))


class BlueprintUERenderer(IRenderer):
    """模拟 UE 编辑器 Ctrl+C 复制的蓝图文本格式。

    与 blueprint_text 的区别：
    - blueprint_ue_text: 输出 Begin Object / End Object 块、CustomProperties Pin、LinkedTo 引用
    - blueprint_text: 输出执行链、反编译函数、紧凑节点列表

    输出应避免 Python repr（如 StructValue(...)、TextValue(...)），
    所有值通过 _format_ue_value() 格式化为 UE 风格字符串。
    """

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []

        lines.append(f'Begin Object Class="{ir.header.package_class}" Name="{ir.header.package_name}"')

        for export in ir.exports:
            lines.append(f'   Begin Object Class="{export.object_class}" Name="{export.object_name}"')

            if export.parent_class:
                lines.append(f'      SuperClass="{export.parent_class}"')

            if export.properties:
                for prop in export.properties:
                    val = _format_ue_value(prop.value)
                    lines.append(f"      {prop.name}={val}")

            # 节点信息
            for graph in export.graphs:
                for node in graph.nodes:
                    guid_upper = node.node_guid.upper() if node.node_guid else ""
                    lines.append(f'   Begin Object Name="{node.node_class}"')
                    lines.append(f"      NodeGuid={guid_upper}")
                    if node.node_comment:
                        lines.append(f'      NodeComment="{_escape_ue_value(node.node_comment)}"')
                    for pin in node.pins:
                        pin_id = pin.linked_to[0][:8].upper() if pin.linked_to else ""
                        lines.append(
                            f'      Pin: {pin.pin_name} ({pin.pin_type}) '
                            f'LinkedTo=({pin_id})' if pin.linked_to else
                            f"      Pin: {pin.pin_name} ({pin.pin_type})"
                        )
                    lines.append("   End Object")

            lines.append("   End Object")

        lines.append("End Object")
        return "\n".join(lines)

    @property
    def format_name(self) -> str:
        return "blueprint_ue_text"


register_renderer("blueprint_ue_text", BlueprintUERenderer)
