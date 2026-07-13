"""
节点类型特定数据类 — K2Node 子类继承 UEdGraphNode。

本模块定义的类是 UE 二进制格式的序列化模型，用于 serializers 层
从 archive 读取数据时构建实例。序列化逻辑位于 serializers/graph.py。

Per D-04: 节点继承结构，子类通过 super() 获取基类字段。
Per D-05: class_name 字段用于 match/case 类型分派。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .core import UEdGraphNode, FMemberReference


@dataclass
class K2NodeCallFunction(UEdGraphNode):
    """K2Node_CallFunction 函数调用节点。"""
    function_reference: FMemberReference | None = None
    b_defaults_to_pure: bool = False


@dataclass
class K2NodeEvent(UEdGraphNode):
    """K2Node_Event 事件节点。"""
    event_reference: FMemberReference | None = None
    b_override_function: bool = False


@dataclass
class K2NodeKnot(UEdGraphNode):
    """K2Node_Knot 重定向节点，无额外字段。"""


@dataclass
class EdGraphNodeComment(UEdGraphNode):
    """EdGraphNode_Comment 注释节点。"""
    comment_color: tuple[float, float, float, float] = (0.05, 0.05, 0.05, 1.0)
    node_width: int = 0
    node_height: int = 0
    font_size: int = 14


@dataclass
class K2NodeEnhancedInputAction(UEdGraphNode):
    """K2Node_EnhancedInputAction 输入动作节点。"""
    input_action_path: str = ""
    trigger_events: dict[str, str] = field(default_factory=dict)


@dataclass
class K2NodeFunctionEntry(UEdGraphNode):
    """K2Node_FunctionEntry 函数入口节点。"""
    function_reference: FMemberReference | None = None
    extra_flags: int = 0
    b_is_editable: bool = False
