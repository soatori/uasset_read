"""
节点类型特定数据类 — 5 种 K2Node 子类继承 UEdGraphNode。

Per D-04: 节点继承结构，子类通过 super() 获取基类字段。
Per D-05: class_name 字段用于 match/case 类型分派。
Per D-06: 数据和序列化解耦。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Self, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectImport, ObjectExport

from .core import UEdGraphNode, FMemberReference


@dataclass
class K2NodeCallFunction(UEdGraphNode):
    """K2Node_CallFunction 函数调用节点。"""
    function_reference: Optional[FMemberReference] = None
    b_defaults_to_pure: bool = False

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        import_map: List[ObjectImport],
        export_map: List[ObjectExport]
    ) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_call_function
        return read_k2node_call_function(archive, name_map, import_map, export_map)


@dataclass
class K2NodeEvent(UEdGraphNode):
    """K2Node_Event 事件节点。"""
    event_reference: Optional[FMemberReference] = None
    b_override_function: bool = False

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        import_map: List[ObjectImport],
        export_map: List[ObjectExport]
    ) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_event
        return read_k2node_event(archive, name_map, import_map, export_map)


@dataclass
class K2NodeKnot(UEdGraphNode):
    """K2Node_Knot 重定向节点，无额外字段。"""

    @classmethod
    def from_archive(cls, archive: FArchive) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_knot
        return read_k2node_knot(archive)


@dataclass
class EdGraphNodeComment(UEdGraphNode):
    """EdGraphNode_Comment 注释节点。"""
    comment_color: Tuple[float, float, float, float] = (0.05, 0.05, 0.05, 1.0)
    node_width: int = 0
    node_height: int = 0
    font_size: int = 14

    @classmethod
    def from_archive(cls, archive: FArchive) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_edgraph_node_comment
        return read_edgraph_node_comment(archive)


@dataclass
class K2NodeEnhancedInputAction(UEdGraphNode):
    """K2Node_EnhancedInputAction 输入动作节点。"""
    input_action_path: str = ""
    trigger_events: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_enhanced_input
        return read_k2node_enhanced_input(archive, name_map)
