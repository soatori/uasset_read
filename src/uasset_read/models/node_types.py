"""
节点类型特定数据类 — 5 种 K2Node 子类继承 UEdGraphNode。

Per D-04: 节点继承结构，子类通过 super() 获取基类字段。
Per D-05: class_name 字段用于 match/case 类型分派。
Per D-06: 数据和序列化解耦。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, TYPE_CHECKING

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
    ) -> "K2NodeCallFunction":
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
    ) -> "K2NodeEvent":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_event
        return read_k2node_event(archive, name_map, import_map, export_map)


@dataclass
class K2NodeKnot(UEdGraphNode):
    """K2Node_Knot 重定向节点，无额外字段。"""

    @classmethod
    def from_archive(cls, archive: FArchive) -> "K2NodeKnot":
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
    def from_archive(cls, archive: FArchive) -> "EdGraphNodeComment":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_edgraph_node_comment
        return read_edgraph_node_comment(archive)


@dataclass
class K2NodeEnhancedInputAction(UEdGraphNode):
    """K2Node_EnhancedInputAction 输入动作节点。"""
    input_action_path: str = ""
    trigger_events: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeEnhancedInputAction":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_enhanced_input
        return read_k2node_enhanced_input(archive, name_map)


@dataclass
class K2NodeFunctionEntry(UEdGraphNode):
    """K2Node_FunctionEntry 函数入口节点。"""
    function_reference: Optional[FMemberReference] = None
    extra_flags: int = 0
    b_is_editable: bool = False

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        import_map: List[ObjectImport],
        export_map: List[ObjectExport]
    ) -> "K2NodeFunctionEntry":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_functionentry
        return read_k2node_functionentry(archive, name_map, import_map, export_map)


@dataclass
class K2NodeMessage(UEdGraphNode):
    """K2Node_Message 消息调用节点。"""
    message_name: str = ""
    message_target: Optional[FMemberReference] = None

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        import_map: List[ObjectImport],
        export_map: List[ObjectExport]
    ) -> "K2NodeMessage":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_message
        return read_k2node_message(archive, name_map, import_map, export_map)


@dataclass
class K2NodeCallDelegate(UEdGraphNode):
    """K2Node_CallDelegate 委托调用节点。"""
    delegate_name: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeCallDelegate":
        from uasset_read.serializers.graph import read_k2node_call_delegate
        return read_k2node_call_delegate(archive, name_map)


@dataclass
class K2NodeCallArrayFunction(UEdGraphNode):
    """K2Node_CallArrayFunction 数组操作节点。"""
    function_name: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeCallArrayFunction":
        from uasset_read.serializers.graph import read_k2node_call_array_function
        return read_k2node_call_array_function(archive, name_map)


@dataclass
class K2NodeCallParentFunction(UEdGraphNode):
    """K2Node_CallParentFunction 调用父类函数节点。"""
    function_name: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeCallParentFunction":
        from uasset_read.serializers.graph import read_k2node_call_parent_function
        return read_k2node_call_parent_function(archive, name_map)


@dataclass
class K2NodeFunctionResult(UEdGraphNode):
    """K2Node_FunctionResult 函数返回值节点。"""
    function_name: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeFunctionResult":
        from uasset_read.serializers.graph import read_k2node_function_result
        return read_k2node_function_result(archive, name_map)


@dataclass
class K2NodeCreateWidget(UEdGraphNode):
    """K2Node_CreateWidget 创建 UI 控件节点。"""
    widget_class: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeCreateWidget":
        from uasset_read.serializers.graph import read_k2node_create_widget
        return read_k2node_create_widget(archive, name_map)


@dataclass
class K2NodeAddDelegate(UEdGraphNode):
    """K2Node_AddDelegate 添加委托绑定节点。"""
    delegate_name: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeAddDelegate":
        from uasset_read.serializers.graph import read_k2node_add_delegate
        return read_k2node_add_delegate(archive, name_map)


@dataclass
class K2NodeMacroInstance(UEdGraphNode):
    """K2Node_MacroInstance 宏实例节点。"""
    macro_name: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeMacroInstance":
        from uasset_read.serializers.graph import read_k2node_macro_instance
        return read_k2node_macro_instance(archive, name_map)


@dataclass
class K2NodeAssignDelegate(UEdGraphNode):
    """K2Node_AssignDelegate 委托赋值节点。"""
    delegate_name: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeAssignDelegate":
        from uasset_read.serializers.graph import read_k2node_assign_delegate
        return read_k2node_assign_delegate(archive, name_map)


@dataclass
class K2NodeGetDataTableRow(UEdGraphNode):
    """K2Node_GetDataTableRow 数据表行获取节点。"""
    data_table: Optional[object] = None
    row_struct_name: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeGetDataTableRow":
        from uasset_read.serializers.graph import read_k2node_get_data_table_row
        return read_k2node_get_data_table_row(archive, name_map)


@dataclass
class K2NodeLoadAsset(UEdGraphNode):
    """K2Node_LoadAsset 异步资产加载节点。"""
    asset_type: Optional[object] = None

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeLoadAsset":
        from uasset_read.serializers.graph import read_k2node_load_asset
        return read_k2node_load_asset(archive, name_map)


@dataclass
class K2NodeSpawnActorFromClass(UEdGraphNode):
    """K2Node_SpawnActorFromClass Actor 生成节点。"""
    spawn_class: Optional[object] = None

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> "K2NodeSpawnActorFromClass":
        from uasset_read.serializers.graph import read_k2node_spawn_actor_from_class
        return read_k2node_spawn_actor_from_class(archive, name_map)
