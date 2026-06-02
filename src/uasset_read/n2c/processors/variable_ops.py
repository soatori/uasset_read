"""Variable/Delegate 扩展节点处理器 — 变量与委托操作补充。

覆盖 K2Node_LocalVariable、K2Node_StructMemberGet、
K2Node_StructMemberSet、K2Node_SetFieldsInStruct、
K2Node_CreateDelegate、K2Node_ClearDelegate、
K2Node_RemoveDelegate、K2Node_DelegateSet。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class LocalVariableProcessor(N2CNodeProcessor):
    """处理 K2Node_LocalVariable 局部变量节点。

    提取局部变量名称和类型。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.LocalVariable]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["variable_scope"] = "local"

        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            var_name = data.get("variable_name") or data.get("member_name")
            if var_name:
                definition.extra_data["variable_name"] = var_name
            var_type = data.get("variable_type")
            if var_type:
                definition.extra_data["variable_type"] = str(var_type)
        else:
            var_name = getattr(data, "variable_name", None) or getattr(data, "member_name", None)
            if var_name:
                definition.extra_data["variable_name"] = var_name
            var_type = getattr(data, "variable_type", None)
            if var_type:
                definition.extra_data["variable_type"] = str(var_type)


class StructMemberGetProcessor(N2CNodeProcessor):
    """处理 K2Node_StructMemberGet 结构体成员读取节点。

    提取结构体成员名称。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.StructMemberGet]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "get_member"

        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            member_name = data.get("member_name") or data.get("field_name")
            if member_name:
                definition.extra_data["member_name"] = member_name
            struct_type = data.get("struct_type")
            if struct_type:
                definition.extra_data["struct_type"] = struct_type
        else:
            member_name = getattr(data, "member_name", None) or getattr(data, "field_name", None)
            if member_name:
                definition.extra_data["member_name"] = member_name
            struct_type = getattr(data, "struct_type", None)
            if struct_type:
                definition.extra_data["struct_type"] = struct_type


class StructMemberSetProcessor(N2CNodeProcessor):
    """处理 K2Node_StructMemberSet 结构体成员写入节点。

    提取结构体成员名称和赋值方向。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.StructMemberSet]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "set_member"

        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            member_name = data.get("member_name") or data.get("field_name")
            if member_name:
                definition.extra_data["member_name"] = member_name
            struct_type = data.get("struct_type")
            if struct_type:
                definition.extra_data["struct_type"] = struct_type
        else:
            member_name = getattr(data, "member_name", None) or getattr(data, "field_name", None)
            if member_name:
                definition.extra_data["member_name"] = member_name
            struct_type = getattr(data, "struct_type", None)
            if struct_type:
                definition.extra_data["struct_type"] = struct_type


class SetFieldsInStructProcessor(N2CNodeProcessor):
    """处理 K2Node_SetFieldsInStruct 结构体字段批量设置节点。

    同时设置多个结构体字段。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.SetFieldsInStruct]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "set_fields_in_struct"


class CreateDelegateProcessor(N2CNodeProcessor):
    """处理 K2Node_CreateDelegate 委托创建节点。

    提取委托绑定的函数引用。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.CreateDelegate]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "create_delegate"

        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            delegate_name = data.get("delegate_name")
            if delegate_name:
                definition.extra_data["delegate_name"] = delegate_name
            func_ref = data.get("function_reference")
            if func_ref:
                if isinstance(func_ref, dict):
                    definition.extra_data["function_name"] = func_ref.get("member_name", "")
                else:
                    definition.extra_data["function_name"] = getattr(func_ref, "member_name", "")
        else:
            delegate_name = getattr(data, "delegate_name", None)
            if delegate_name:
                definition.extra_data["delegate_name"] = delegate_name


class ClearDelegateProcessor(N2CNodeProcessor):
    """处理 K2Node_ClearDelegate 委托清除节点。

    从多播委托中移除所有绑定。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.ClearDelegate]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "clear_delegate"

        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            delegate_name = data.get("delegate_name")
            if delegate_name:
                definition.extra_data["delegate_name"] = delegate_name
        else:
            delegate_name = getattr(data, "delegate_name", None)
            if delegate_name:
                definition.extra_data["delegate_name"] = delegate_name


class RemoveDelegateProcessor(N2CNodeProcessor):
    """处理 K2Node_RemoveDelegate 委托移除节点。

    从多播委托中移除指定绑定。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.RemoveDelegate]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "remove_delegate"

        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            delegate_name = data.get("delegate_name")
            if delegate_name:
                definition.extra_data["delegate_name"] = delegate_name
        else:
            delegate_name = getattr(data, "delegate_name", None)
            if delegate_name:
                definition.extra_data["delegate_name"] = delegate_name


class DelegateSetProcessor(N2CNodeProcessor):
    """处理 K2Node_DelegateSet 委托赋值节点。

    设置委托的绑定。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.DelegateSet]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "set_delegate"

        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            delegate_name = data.get("delegate_name")
            if delegate_name:
                definition.extra_data["delegate_name"] = delegate_name
        else:
            delegate_name = getattr(data, "delegate_name", None)
            if delegate_name:
                definition.extra_data["delegate_name"] = delegate_name
