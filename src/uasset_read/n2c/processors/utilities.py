"""Utility 节点处理器 — 异步、时间线、文本、数学、枚举操作。

覆盖 K2Node_AsyncAction、K2Node_Timeline、K2Node_FormatText、
K2Node_MathExpression、K2Node_GetEnumeratorName、
K2Node_GetEnumeratorNameAsString、K2Node_GetNumEnumEntries、
K2Node_EnumEquality、K2Node_EnumInequality。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class AsyncActionProcessor(N2CNodeProcessor):
    """处理 K2Node_AsyncAction 异步动作节点。

    提取异步任务类型和函数引用。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.AsyncAction]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["async"] = True

        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            func_ref = data.get("function_reference")
            if func_ref:
                if isinstance(func_ref, dict):
                    if "member_name" in func_ref:
                        definition.extra_data["function_name"] = func_ref["member_name"]
                    if "member_parent" in func_ref:
                        definition.extra_data["function_parent"] = func_ref["member_parent"]
                else:
                    if hasattr(func_ref, "member_name"):
                        definition.extra_data["function_name"] = func_ref.member_name
                    if hasattr(func_ref, "member_parent"):
                        definition.extra_data["function_parent"] = func_ref.member_parent
        else:
            func_ref = getattr(data, "function_reference", None)
            if func_ref:
                if isinstance(func_ref, dict):
                    if "member_name" in func_ref:
                        definition.extra_data["function_name"] = func_ref["member_name"]
                    if "member_parent" in func_ref:
                        definition.extra_data["function_parent"] = func_ref["member_parent"]
                else:
                    if hasattr(func_ref, "member_name"):
                        definition.extra_data["function_name"] = func_ref.member_name
                    if hasattr(func_ref, "member_parent"):
                        definition.extra_data["function_parent"] = func_ref.member_parent


class TimelineProcessor(N2CNodeProcessor):
    """处理 K2Node_Timeline 时间线节点。

    提取时间线名称和播放方向。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.Timeline]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["timeline"] = True

        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            timeline_name = data.get("timeline_name") or data.get("member_name")
            if timeline_name:
                definition.extra_data["timeline_name"] = timeline_name
            direction = data.get("direction")
            if direction:
                definition.extra_data["direction"] = direction
        else:
            timeline_name = getattr(data, "timeline_name", None) or getattr(data, "member_name", None)
            if timeline_name:
                definition.extra_data["timeline_name"] = timeline_name
            direction = getattr(data, "direction", None)
            if direction:
                definition.extra_data["direction"] = direction


class FormatTextProcessor(N2CNodeProcessor):
    """处理 K2Node_FormatText 文本格式化节点。

    提取格式化模板字符串。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.FormatText]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            format_string = data.get("format_string") or data.get("pattern")
            if format_string:
                definition.extra_data["format_string"] = format_string
            # 提取参数占位符数量
            args = data.get("arguments") or data.get("args")
            if args:
                definition.extra_data["arg_count"] = len(args) if isinstance(args, (list, tuple)) else 1
        else:
            format_string = getattr(data, "format_string", None) or getattr(data, "pattern", None)
            if format_string:
                definition.extra_data["format_string"] = format_string


class MathExpressionProcessor(N2CNodeProcessor):
    """处理 K2Node_MathExpression 数学表达式节点。

    提取数学表达式内容。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.MathExpression]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            expression = data.get("expression") or data.get("math_expression")
            if expression:
                definition.extra_data["expression"] = expression
        else:
            expression = getattr(data, "expression", None) or getattr(data, "math_expression", None)
            if expression:
                definition.extra_data["expression"] = str(expression)


class GetEnumeratorNameProcessor(N2CNodeProcessor):
    """处理 K2Node_GetEnumeratorName 枚举值名称获取节点。

    将枚举值转换为字符串名称。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.GetEnumeratorName]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["enum_operation"] = "get_name"


class GetEnumeratorNameAsStringProcessor(N2CNodeProcessor):
    """处理 K2Node_GetEnumeratorNameAsString 枚举值字符串获取节点。

    将枚举值转换为 FString。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.GetEnumeratorNameAsString]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["enum_operation"] = "get_name_as_string"


class GetNumEnumEntriesProcessor(N2CNodeProcessor):
    """处理 K2Node_GetNumEnumEntries 枚举条目数获取节点。

    返回枚举类型的条目总数。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.GetNumEnumEntries]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["enum_operation"] = "get_num_entries"


class EnumComparisonProcessor(N2CNodeProcessor):
    """处理枚举比较节点（相等/不等）。

    覆盖 EnumEquality 和 EnumInequality。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.EnumEquality, N2CNodeType.EnumInequality]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if definition.node_type == N2CNodeType.EnumEquality:
            definition.extra_data["comparison"] = "equals"
        else:
            definition.extra_data["comparison"] = "not_equals"
