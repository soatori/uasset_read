"""蓝图 Node 二进制序列化器 — UEdGraphNode, K2Node 读取函数。

从 serializers/graph.py 拆分而来，包含所有节点相关的读取逻辑。
"""
from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import (
    MAX_PINS_PER_NODE, UE_NONE_SENTINEL,
)
from uasset_read.exceptions import ParseError, ErrorContext
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded
from uasset_read.models.core import UEdGraphNode, UEdGraphPin, FMemberReference

from uasset_read.serializers.graph_helpers import (
    _read_guid, _rcn, _gac, _get_thread_local,
    _read_tag_bool, _read_tag_i32, _read_tag_fname,
    read_ftext_with_history,
)
from uasset_read.serializers.graph_pin import read_ue_graph_pin

logger = logging.getLogger(__name__)

# ============================================================================
# FMemberReference 读取
# ============================================================================

def read_fmember_reference(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> FMemberReference:
    """读取 FMemberReference（MemberReference.h L74-95）。"""
    member_parent_index = archive.read_i32("MemberRef.MemberParent")
    member_parent: Optional[str] = None
    if member_parent_index != 0:
        member_parent = _rcn(
            PackageIndex(member_parent_index), import_map, export_map, linker
        )

    _member_scope = archive.read_fstring("MemberRef.MemberScope")  # noqa: F841 - protocol read
    member_name = archive.read_name(name_map, "MemberRef.MemberName")
    member_guid = _read_guid(archive, uppercase=False)
    b_self_context = archive.read_bool("MemberRef.bSelfContext")
    _b_was_deprecated = archive.read_bool("MemberRef.bWasDeprecated")

    return FMemberReference(
        member_parent=member_parent,
        member_name=member_name,
        member_guid=member_guid,
        b_self_context=b_self_context,
    )

# ============================================================================
# 5 种节点类型读取器
# ============================================================================

def read_k2node_call_function(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
    function_reference: Optional[FMemberReference] = None,
) -> Dict[str, Any]:
    """读取 K2Node_CallFunction 特有字段，返回字典（作为 node_data）。

    如果 function_reference 已在 PropertyTag 层解析（script_serial），直接使用；
    否则从 archive 当前位置读取 FMemberReference。

    参考 UE C++ FK2Node_CallFunction::Serialize() 实现。
    """
    # D-11: PropertyTag 层已正确解析 FunctionReference，优先使用
    if function_reference is None:
        function_reference = read_fmember_reference(archive, name_map, import_map, export_map, linker)

    b_defaults_to_pure = archive.read_bool("K2Node_CallFunction.bDefaultsToPure")
    return {
        "function_reference": function_reference,
        "b_defaults_to_pure": b_defaults_to_pure,
    }

def read_k2node_event(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
    event_reference: Optional[FMemberReference] = None,
    b_override_function: Optional[bool] = None,
    b_internal_event: Optional[bool] = None,
    custom_function_name: Optional[str] = None,
    function_flags: Optional[int] = None,
) -> Dict[str, Any]:
    """读取 K2Node_Event 特有字段，返回字典（作为 node_data）。

    如果 event_reference、b_override_function 等字段已在 PropertyTag 层解析（script_serial），
    直接使用；fallback 读取必须受 script_serial_size / 字段 trace 验证保护。

    返回字段：
    - event_reference: FMemberReference
    - b_override_function: bool
    - b_internal_event: bool (新增)
    - custom_function_name: str (新增)
    - function_flags: int (新增)

    参考 UE C++ FK2Node_Event::Serialize() 实现。
    """
    # D-11: PropertyTag 层已正确解析 EventReference，优先使用
    if event_reference is None:
        event_reference = read_fmember_reference(archive, name_map, import_map, export_map, linker)

    # b_override_function 优先使用 PropertyTag 值，不再盲读
    # 只有 PropertyTag 未提供时才考虑 fallback，且 fallback 必须受验证保护
    if b_override_function is None:
        # Legacy fallback: 仅在确认有剩余字节时读取
        # 标记 source 为 "legacy_fallback"，便于诊断追踪
        try:
            b_override_function = archive.read_bool()
            logger.debug(
                "K2Node_Event b_override_function read from legacy fallback (bool at pos %d)",
                archive.tell() - 4
            )
        except (struct.error, OSError, ValueError) as e:
            logger.debug(
                "K2Node_Event b_override_function fallback failed: %s, defaulting to False",
                e
            )
            b_override_function = False

    return {
        "event_reference": event_reference,
        "b_override_function": b_override_function,
        "b_internal_event": b_internal_event if b_internal_event is not None else False,
        "custom_function_name": custom_function_name or "",
        "function_flags": function_flags if function_flags is not None else 0,
        "is_event": True,
    }

def read_k2node_knot(archive: FArchive) -> Dict[str, Any]:
    """K2Node_Knot 无额外字段。"""
    return {}

def read_edgraph_node_comment(raw_properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """读取 EdGraphNode_Comment 特有字段，返回字典（作为 node_data）。

    UE5 样本中注释节点的颜色和尺寸位于 tagged properties。旧实现继续从
    尾部二进制读 float/int，容易把后续字段错读成荒谬尺寸。
    """
    raw_properties = raw_properties or {}
    return {
        "comment_color": raw_properties.get("CommentColor"),
        "node_width": raw_properties.get("NodeWidth"),
        "node_height": raw_properties.get("NodeHeight"),
        "font_size": raw_properties.get("FontSize"),
        "comment_depth": raw_properties.get("CommentDepth"),
    }

def _build_trigger_events_from_pins(pins: List["UEdGraphPin"]) -> Dict[str, str]:
    """从 EnhancedInputAction 节点的 pins 提取 trigger_events 映射。

    遍历 exec 方向的输出 pin，将 pin 名称通过 ETRIGGER_EVENT_PIN_MAP
    映射为 ETriggerEvent 枚举字符串值。
    """
    from uasset_read.constants import ETRIGGER_EVENT_PIN_MAP

    trigger_events = {}
    for pin in pins:
        pin_category = getattr(pin.pin_type, 'pin_category', '') if pin.pin_type else ''
        direction = getattr(pin, 'direction', None)
        pin_name = getattr(pin, 'pin_name', '')
        
        # Check if this is an output exec pin or if pin_category matches trigger events
        is_exec_output = (pin_category == "exec" and direction == 1)
        is_trigger_pin = (pin_name in ETRIGGER_EVENT_PIN_MAP)
        is_trigger_category = (pin_category in ETRIGGER_EVENT_PIN_MAP)
        
        if is_exec_output or is_trigger_pin or is_trigger_category:
            # Use pin_name if available and valid, otherwise use pin_category
            trigger_name = pin_name if pin_name and pin_name in ETRIGGER_EVENT_PIN_MAP else pin_category
            if trigger_name in ETRIGGER_EVENT_PIN_MAP:
                trigger_events[trigger_name] = ETRIGGER_EVENT_PIN_MAP[trigger_name]
    return trigger_events

def read_k2node_enhanced_input(
    archive: FArchive,
    name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_EnhancedInputAction 特有字段，返回字典（作为 node_data）。

    从 PropertyTag 层获取 AdvancedPinDisplay、InputAction 短名等字段。

    返回字段：
    - input_action_path: 完整对象路径
    - input_action_short_name: 短名（如 "IA_Move"）
    - input_action_package_index: 原始 FPackageIndex
    - advanced_pin_display: 格式化枚举名（如 "Hidden"）
    - advanced_pin_display_raw: 原始 int 值
    """
    raw_properties = raw_properties or {}

    # InputAction 从 PropertyTag 获取（已在 read_ue_graph_node 中解析）
    input_action_path = raw_properties.get("InputAction") or ""
    input_action_short_name = raw_properties.get("InputActionShortName") or ""
    input_action_package_index = raw_properties.get("InputActionPackageIndex", 0)

    # 如果 PropertyTag 未提供，尝试从 archive 读取
    if not input_action_path:
        try:
            input_action_path = archive.read_fstring()
            # 从路径提取短名
            if input_action_path:
                input_action_short_name = input_action_path.split(".")[-1].split("'")[0]
        except (struct.error, OSError, ValueError):
            input_action_path = ""

    # AdvancedPinDisplay 从 PropertyTag 获取
    advanced_pin_display_raw = raw_properties.get("AdvancedPinDisplay", 0)
    advanced_pin_display = raw_properties.get("AdvancedPinDisplayFormatted", "Default")

    return {
        "input_action_path": input_action_path,
        "input_action_short_name": input_action_short_name,
        "input_action_package_index": input_action_package_index,
        "advanced_pin_display": advanced_pin_display,
        "advanced_pin_display_raw": advanced_pin_display_raw,
    }

def read_k2node_functionentry(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
    function_reference: Optional[FMemberReference] = None,
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_FunctionEntry 特有字段，返回字典（作为 node_data）。

    从 PropertyTag 层获取 ExtraFlags、bIsEditable。

    FunctionReference 已在 read_ue_graph_node() 中从 PropertyTag 解析。

    返回字段：
    - function_reference: FMemberReference
    - extra_flags: int
    - b_is_editable: bool
    """
    raw_properties = raw_properties or {}

    extra_flags = raw_properties.get("ExtraFlags", 0)
    b_is_editable = raw_properties.get("bIsEditable", False)

    return {
        "function_reference": function_reference,
        "extra_flags": extra_flags,
        "b_is_editable": b_is_editable,
    }

def read_k2node_message(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> Dict[str, Any]:
    """读取 K2Node_Message 特有字段。"""
    result = {}

    try:
        message_name_idx = archive.read_i32()
        if 0 <= message_name_idx < len(name_map):
            result["message_name"] = name_map[message_name_idx]
        else:
            result["message_name"] = f"Message_{message_name_idx}"
    except (struct.error, OSError, ValueError) as e:
        logger.debug("K2Node_Message read failed: %s", e)
        result["message_name"] = "Unknown"

    return result

def read_k2node_call_delegate(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """读取 K2Node_CallDelegate 字段。"""
    result = {}
    try:
        delegate_idx = archive.read_i32()
        if 0 <= delegate_idx < len(name_map):
            result["delegate_name"] = name_map[delegate_idx]
    except (struct.error, OSError, ValueError) as e:
        logger.debug("K2Node_CallDelegate read failed: %s", e)
    return result

def _read_k2node_function_reference(
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """从 raw_properties 提取 FunctionReference。"""
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    func_ref = raw_properties.get("FunctionReference")
    if func_ref is not None:
        result["function_reference"] = func_ref

    return result

def read_k2node_call_array_function(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_CallArrayFunction 特有字段。"""
    return _read_k2node_function_reference(raw_properties)

def read_k2node_call_parent_function(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_CallParentFunction 特有字段。"""
    return _read_k2node_function_reference(raw_properties)

def read_k2node_function_result(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_FunctionResult 特有字段。"""
    return _read_k2node_function_reference(raw_properties)

def read_k2node_create_widget(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_CreateWidget 特有字段。

    继承自 K2Node_ConstructObjectFromClass，创建 UMG 控件。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # WidgetClass 从 PropertyTag 获取（FPackageIndex → 类名）
    widget_class = raw_properties.get("WidgetClass")
    if widget_class is not None:
        result["widget_class"] = widget_class

    return result

def _read_k2node_delegate_name(
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """从 raw_properties 提取 DelegateName。"""
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    delegate_name = raw_properties.get("DelegateName")
    if delegate_name is not None:
        result["delegate_name"] = delegate_name

    return result

def read_k2node_add_delegate(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_AddDelegate 特有字段。"""
    return _read_k2node_delegate_name(raw_properties)

def read_k2node_macro_instance(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_MacroInstance 特有字段。

    继承自 K2Node_Tunnel，表示宏图表实例。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # MacroGraph 从 PropertyTag 获取（FPackageIndex → 宏图表引用）
    macro_graph = raw_properties.get("MacroGraph")
    if macro_graph is not None:
        result["macro_graph"] = macro_graph

    # Macro 从 PropertyTag 获取（FName → 宏名称）
    macro = raw_properties.get("Macro")
    if macro is not None:
        result["macro_name"] = macro

    # MacroGraphReference 结构化解析（新格式：FGraphReference）
    macro_graph_ref = raw_properties.get("MacroGraphReference")
    if macro_graph_ref is not None:
        result["macro_graph_reference"] = macro_graph_ref

    # ResolvedWildcardType — 通配符引脚解析后的类型
    resolved_wildcard = raw_properties.get("ResolvedWildcardType")
    if resolved_wildcard is not None:
        result["resolved_wildcard_type"] = resolved_wildcard

    return result

def read_k2node_assign_delegate(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_AssignDelegate 特有字段。"""
    return _read_k2node_delegate_name(raw_properties)

def read_k2node_get_data_table_row(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_GetDataTableRow 特有字段。

    从数据表获取行数据。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # DataTable 从 PropertyTag 获取
    data_table = raw_properties.get("DataTable")
    if data_table is not None:
        result["data_table"] = data_table

    # RowStructName 从 PropertyTag 获取
    row_struct = raw_properties.get("RowStructName")
    if row_struct is not None:
        result["row_struct_name"] = row_struct

    return result

def read_k2node_load_asset(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_LoadAsset 特有字段。

    异步加载资产节点。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # AssetType 从 PropertyTag 获取
    asset_type = raw_properties.get("AssetType")
    if asset_type is not None:
        result["asset_type"] = asset_type

    return result

def read_k2node_spawn_actor_from_class(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_SpawnActorFromClass 特有字段。

    继承自 K2Node_ConstructObjectFromClass，生成 Actor。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # Class 从 PropertyTag 获取
    spawn_class = raw_properties.get("Class")
    if spawn_class is not None:
        result["spawn_class"] = spawn_class

    return result

# ============================================================================
# dispatch 处理器 — 统一签名 (ctx: Dict[str, Any]) -> Dict[str, Any]
# ctx 包含: archive, name_map, summary, export_map, import_map, linker,
#           node_refs, raw_properties, class_name, node_export, base_node
# ============================================================================

def _handle_call_function(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """K2Node_CallFunction 分发处理器。"""
    return read_k2node_call_function(
        ctx["archive"], ctx["name_map"], ctx["import_map"], ctx["export_map"], ctx["linker"],
        function_reference=ctx.get("node_refs", {}).get("function_reference"),
    )

def _handle_event(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """K2Node_Event 分发处理器。"""
    refs = ctx.get("node_refs") or {}
    return read_k2node_event(
        ctx["archive"], ctx["name_map"], ctx["import_map"], ctx["export_map"], ctx["linker"],
        event_reference=refs.get("event_reference"),
        b_override_function=refs.get("b_override_function"),
        b_internal_event=refs.get("b_internal_event"),
        custom_function_name=refs.get("custom_function_name"),
        function_flags=refs.get("function_flags"),
    )

def _handle_comment(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """EdGraphNode_Comment 分发处理器，含属性回写。"""
    node_data = read_edgraph_node_comment(ctx.get("raw_properties"))
    base_node = ctx["base_node"]
    if isinstance(node_data, dict):
        for attr, key in (
            ("comment_color", "comment_color"),
            ("node_width", "node_width"),
            ("node_height", "node_height"),
            ("font_size", "font_size"),
        ):
            value = node_data.get(key)
            if value is not None:
                setattr(base_node, attr, value)
    return node_data

def _handle_enhanced_input(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """K2Node_EnhancedInputAction 分发处理器，含 trigger_events 提取。"""
    node_data = read_k2node_enhanced_input(
        ctx["archive"], ctx["name_map"], ctx.get("raw_properties"),
    )
    if isinstance(node_data, dict):
        node_data["trigger_events"] = _build_trigger_events_from_pins(ctx["base_node"].pins)
    return node_data

def _handle_function_entry(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """K2Node_FunctionEntry 分发处理器。"""
    fr = ctx.get("node_refs", {}).get("function_reference")
    return read_k2node_functionentry(
        ctx["archive"], ctx["name_map"], ctx["import_map"], ctx["export_map"], ctx["linker"],
        function_reference=fr,
        raw_properties=ctx.get("raw_properties"),
    )

def _handle_full_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """AnimGraphNode 类型的分发处理器。"""
    return _read_anim_graph_node(
        ctx["archive"], ctx["name_map"], ctx["summary"],
        ctx["export_map"], ctx["import_map"], ctx["linker"],
        ctx["class_name"], ctx.get("raw_properties"),
    )

def _handle_unknown_type(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """未知节点类型的兜底处理器。"""
    raw = ctx.get("raw_properties")
    return {"_raw_properties": raw} if raw else {}

# 通用处理器：只需 archive + name_map + raw_properties 的节点类型
def _handle_simple_raw_props(ctx: Dict[str, Any], reader) -> Dict[str, Any]:
    return reader(ctx["archive"], ctx["name_map"], raw_properties=ctx.get("raw_properties"))

def _handle_simple_full(ctx: Dict[str, Any], reader) -> Dict[str, Any]:
    return reader(ctx["archive"], ctx["name_map"],
                  ctx["import_map"], ctx["export_map"], ctx["linker"])

# 节点类型 → 处理器映射
_NODE_TYPE_HANDLERS: Dict[str, Any] = {
    "K2Node_CallFunction": _handle_call_function,
    "K2Node_Event": _handle_event,
    "K2Node_Knot": lambda ctx: read_k2node_knot(ctx["archive"]),
    "EdGraphNode_Comment": _handle_comment,
    "K2Node_EnhancedInputAction": _handle_enhanced_input,
    "K2Node_FunctionEntry": _handle_function_entry,
    "K2Node_Message": lambda ctx: _handle_simple_full(ctx, read_k2node_message),
    "K2Node_CallDelegate": lambda ctx: read_k2node_call_delegate(ctx["archive"], ctx["name_map"]),
    "K2Node_CallArrayFunction": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_call_array_function),
    "K2Node_CallParentFunction": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_call_parent_function),
    "K2Node_FunctionResult": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_function_result),
    "K2Node_CreateWidget": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_create_widget),
    "K2Node_AddDelegate": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_add_delegate),
    "K2Node_MacroInstance": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_macro_instance),
    "K2Node_AssignDelegate": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_assign_delegate),
    "K2Node_GetDataTableRow": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_get_data_table_row),
    "K2Node_LoadAsset": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_load_asset),
    "K2Node_SpawnActorFromClass": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_spawn_actor_from_class),
}

# ============================================================================
# AnimGraphNode 读取
# ============================================================================

def _read_anim_graph_node(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"],
    class_name: str,
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 AnimGraphNode 类型节点的数据。

    关键属性：
    - EditorStateMachineGraph: 状态机的子图 (UAnimationStateMachineGraph)
    - BoundGraph: 状态的子图 (UEdGraph)
    - Node: 动画节点运行时数据 (FAnimNode_StateMachine 等)
    """
    result: Dict[str, Any] = {
        "node_type": class_name,
    }

    if not raw_properties:
        return result

    # 提取子图引用
    subgraph_refs = {}
    for key in ("EditorStateMachineGraph", "BoundGraph"):
        pkg_idx = raw_properties.get(key)
        if pkg_idx and isinstance(pkg_idx, int) and pkg_idx != 0:
            # 解析 PackageIndex 为对象引用
            try:
                if linker is not None:
                    obj_ref = linker.resolve_package_index(PackageIndex(pkg_idx))
                    if obj_ref is not None:
                        subgraph_refs[key] = {
                            "package_index": pkg_idx,
                            "object_name": getattr(obj_ref, "object_name", ""),
                            "class_name": getattr(obj_ref, "class_name", ""),
                        }
                else:
                    # 无 linker 时，尝试从 export_map 解析
                    if pkg_idx > 0 and pkg_idx <= len(export_map):
                        obj_export = export_map[pkg_idx - 1]
                        subgraph_refs[key] = {
                            "package_index": pkg_idx,
                            "object_name": obj_export.object_name,
                            "class_name": _gac(obj_export, import_map, export_map, linker) or "",
                        }
            except (KeyError, IndexError, AttributeError):
                subgraph_refs[key] = {"package_index": pkg_idx, "error": "resolve_failed"}

    if subgraph_refs:
        result["subgraph_references"] = subgraph_refs

    # 提取其他 AnimGraphNode 特有属性
    node_data = raw_properties.get("Node")
    if node_data and isinstance(node_data, dict):
        result["anim_node_data"] = node_data

    # 状态机特有属性
    if "StateMachineIndexInClass" in raw_properties:
        result["state_machine_index"] = raw_properties["StateMachineIndexInClass"]

    return result

# ============================================================================
# 节点工厂
# ============================================================================

def create_node_from_archive(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    node_export: ObjectExport,
    base_node: UEdGraphNode,
    raw_properties: Optional[Dict[str, Any]] = None,
    linker: Optional["PackageLinker"] = None,
    node_refs: Optional[Dict[str, Any]] = None,
) -> UEdGraphNode:
    """根据 class_name 分派到对应的节点读取函数（D-07/D-08 工厂模式）。

    使用字典分发替代 if/elif 链。精确匹配优先（_NODE_TYPE_HANDLERS），
    其次前缀匹配（AnimGraphNode_ / AnimState），最后兜底保留 raw_properties。
    """
    class_name = base_node.class_name

    # 如果 base_node 已经携带 _parse_error 标记，跳过分发保护已有信息
    if isinstance(base_node.node_data, dict) and base_node.node_data.get("_parse_error"):
        return base_node

    # 构建统一上下文，供所有处理器按需取用
    ctx: Dict[str, Any] = {
        "archive": archive,
        "name_map": name_map,
        "summary": summary,
        "export_map": export_map,
        "import_map": import_map,
        "linker": linker,
        "node_refs": node_refs,
        "raw_properties": raw_properties,
        "class_name": class_name,
        "node_export": node_export,
        "base_node": base_node,
    }

    # 字典分发：精确匹配
    handler = _NODE_TYPE_HANDLERS.get(class_name)
    if handler is not None:
        base_node.node_data = handler(ctx)
    # 前缀匹配：AnimGraphNode 类型（无法穷举枚举）
    elif class_name.startswith("AnimGraphNode_") or class_name.startswith("AnimState"):
        base_node.node_data = _handle_full_context(ctx)
    elif raw_properties:
        # 未知类型：保留原始 PropertyTag 元数据用于调试和未来扩展
        base_node.node_data = _handle_unknown_type(ctx)

    return base_node

# ============================================================================
# UEdGraphNode 读取
# ============================================================================

def _read_member_reference_from_tags(
    archive: FArchive,
    tag,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> FMemberReference:
    """从 PropertyTag 读取 FMemberReference 结构（FunctionReference/EventReference 共用）。"""
    value_end = tag.value_end_offset or (archive.tell() + tag.size)
    mp_idx = 0
    m_name = ""
    m_guid = ""
    m_self = False

    while archive.tell() < value_end:
        inner = read_property_tag(archive, name_map)
        if inner.name == UE_NONE_SENTINEL:
            break
        if inner.value_end_offset is not None and inner.value_end_offset > value_end:
            raise ParseError(
                f"MemberReference field '{inner.name}' exceeds struct boundary",
                context=ErrorContext(
                    offset=archive.tell(),
                    phase="graph",
                    operation="_read_member_reference_from_tags",
                    context_name="",
                ),
            )

        def _read_inner(inner=inner):
            if inner.name == "MemberParent" and inner.size > 0:
                return archive.read_i32()
            if inner.name == "MemberScope" and inner.size > 0:
                archive.read_fstring()
                return None
            if inner.name == "MemberName":
                return archive.read_name(name_map)
            if inner.name == "MemberGuid" and inner.size > 0:
                return archive.read_bytes(16).hex()
            if inner.name == "bSelfContext":
                return (archive.read_i32() != 0) if inner.size > 0 else (inner.bool_val != 0)
            if inner.name == "bWasDeprecated" and inner.size > 0:
                archive.read_i32()
            return None

        inner_value = read_tag_value_bounded(archive, inner, _read_inner)
        if inner.name == "MemberParent":
            mp_idx = inner_value or 0
        elif inner.name == "MemberName":
            m_name = inner_value or ""
        elif inner.name == "MemberGuid":
            m_guid = inner_value or ""
        elif inner.name == "bSelfContext":
            m_self = bool(inner_value)

    return FMemberReference(
        member_parent=_rcn(PackageIndex(mp_idx), import_map, export_map, linker) if mp_idx != 0 else None,
        member_name=m_name,
        member_guid=m_guid,
        b_self_context=m_self,
    )

# ============================================================================
# node PropertyTag 分发处理器
# ============================================================================

def _handle_node_pos_x(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 NodePosX 标签。"""
    return {"node_pos_x": _read_tag_i32(archive, tag)}


def _handle_node_pos_y(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 NodePosY 标签。"""
    return {"node_pos_y": _read_tag_i32(archive, tag)}


def _handle_node_guid(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 NodeGuid 标签。"""
    if tag.size > 0:
        val = archive.read_bytes(16).hex()
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
        return {"node_guid": val}
    return {}


def _handle_node_comment(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 NodeComment 标签。"""
    if tag.size > 0:
        val = archive.read_fstring()
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
        return {"node_comment": val}
    return {}


def _handle_input_action(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 InputAction 标签。"""
    if tag.size > 0:
        pkg_idx = archive.read_i32()
        input_action_path = (
            _rcn(PackageIndex(pkg_idx), import_map, export_map, linker)
            if pkg_idx != 0 else ""
        )
        raw_properties[tag.name] = input_action_path
        raw_properties["InputActionShortName"] = (
            input_action_path.split(".")[-1].split("'")[0]
            if input_action_path else ""
        )
        raw_properties["InputActionPackageIndex"] = pkg_idx
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
    return {}


def _handle_comment_color(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 CommentColor 标签（RGBA 四分量 float）。"""
    if tag.size >= 16:
        raw_properties[tag.name] = (
            archive.read_f32(),
            archive.read_f32(),
            archive.read_f32(),
            archive.read_f32(),
        )
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
    return {}


def _handle_i32_to_raw(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 I32 类型标签（NodeWidth、NodeHeight、FontSize、CommentDepth、ExtraFlags）。"""
    if tag.size > 0:
        raw_properties[tag.name] = _read_tag_i32(archive, tag)
    return {}


def _handle_bool_to_raw(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理布尔类型标签（bCommentBubbleVisible_InDetailsPanel、bIsEditable）。"""
    raw_properties[tag.name] = _read_tag_bool(archive, tag)
    return {}


def _handle_advanced_pin_display(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 AdvancedPinDisplay 标签（枚举值 + 格式化名称）。"""
    if tag.size > 0:
        raw_val = _read_tag_i32(archive, tag)
        raw_properties[tag.name] = raw_val
        enum_map = {0: "Default", 1: "Hidden", 2: "Shown"}
        raw_properties["AdvancedPinDisplayFormatted"] = enum_map.get(raw_val, f"Unknown({raw_val})")
    return {}


def _handle_override_function(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 bOverrideFunction 标签（同时写入 updates 和 raw_properties）。"""
    val = _read_tag_bool(archive, tag)
    raw_properties[tag.name] = val
    return {"b_override_function": val}


def _handle_internal_event(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 bInternalEvent 标签（同时写入 updates 和 raw_properties）。"""
    val = _read_tag_bool(archive, tag)
    raw_properties[tag.name] = val
    return {"b_internal_event": val}


def _handle_custom_function_name(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 CustomFunctionName 标签（FName，同时写入 updates 和 raw_properties）。"""
    val = _read_tag_fname(archive, tag, name_map)
    raw_properties[tag.name] = val
    return {"custom_function_name": val}


def _handle_function_flags(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 FunctionFlags 标签（同时写入 updates 和 raw_properties）。"""
    if tag.size > 0:
        val = _read_tag_i32(archive, tag)
        raw_properties[tag.name] = val
        return {"function_flags": val}
    return {}


def _handle_fname_to_raw(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 FName 类型标签（CustomGeneratedFunctionName）。"""
    raw_properties[tag.name] = _read_tag_fname(archive, tag, name_map)
    return {}


def _handle_package_index(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 PackageIndex 类型标签（EditorStateMachineGraph、BoundGraph）。"""
    if tag.size > 0:
        pkg_idx = archive.read_i32()
        raw_properties[tag.name] = pkg_idx
        raw_properties[f"{tag.name}PackageIndex"] = pkg_idx
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
    return {}


def _handle_move_mode(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 MoveMode 标签（单字节枚举值）。"""
    if tag.size > 0:
        raw_val = archive.read_u8() if tag.size >= 1 else 0
        raw_properties[tag.name] = raw_val
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
    return {}


def _handle_node_details(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """处理 NodeDetails 标签（FText 带历史记录）。"""
    if tag.size > 0:
        try:
            _flags = archive.read_i32()  # noqa: F841 - protocol read
            history_type_raw = archive.read_u8()
            history_type = history_type_raw - 256 if history_type_raw >= 128 else history_type_raw
            read_ftext_with_history(archive, history_type, tolerant=True)
        except (struct.error, OSError, ValueError) as e:
            logger.debug("读取 NodeDetails FText 失败: %s", e, exc_info=True)
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
        raw_properties[tag.name] = {"size": tag.size, "type": "FText"}
    return {}


# 标签名 → 处理函数的分发字典
_NODE_TAG_HANDLERS: Dict[str, Any] = {
    "NodePosX": _handle_node_pos_x,
    "NodePosY": _handle_node_pos_y,
    "NodeGuid": _handle_node_guid,
    "NodeComment": _handle_node_comment,
    "InputAction": _handle_input_action,
    "CommentColor": _handle_comment_color,
    "NodeWidth": _handle_i32_to_raw,
    "NodeHeight": _handle_i32_to_raw,
    "FontSize": _handle_i32_to_raw,
    "bCommentBubbleVisible_InDetailsPanel": _handle_bool_to_raw,
    "CommentDepth": _handle_i32_to_raw,
    "ExtraFlags": _handle_i32_to_raw,
    "AdvancedPinDisplay": _handle_advanced_pin_display,
    "bOverrideFunction": _handle_override_function,
    "bInternalEvent": _handle_internal_event,
    "bIsEditable": _handle_bool_to_raw,
    "CustomFunctionName": _handle_custom_function_name,
    "FunctionFlags": _handle_function_flags,
    "CustomGeneratedFunctionName": _handle_fname_to_raw,
    "EditorStateMachineGraph": _handle_package_index,
    "BoundGraph": _handle_package_index,
    "MoveMode": _handle_move_mode,
    "NodeDetails": _handle_node_details,
}


def _read_node_property_tag(
    archive: FArchive,
    tag,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"],
    raw_properties: Dict[str, Any],
) -> dict:
    """读取单个 node PropertyTag 并更新局部变量。返回需要更新的 named 属性。"""
    handler = _NODE_TAG_HANDLERS.get(tag.name)
    if handler:
        return handler(archive, tag, name_map, import_map, export_map, linker, raw_properties)

    # 未匹配的标签：有数据时跳过字节，避免偏移错乱
    if tag.size > 0:
        value_start = archive.tell()
        raw_properties[tag.name] = {"size": tag.size, "offset": value_start}
        archive.seek(tag.value_end_offset)

    return {}

def _read_node_pins(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"],
    node_export: ObjectExport,
    node_name: str,
    node_guid: str,
) -> List[UEdGraphPin]:
    """读取节点的 Pins 数组。"""
    pins_offset = node_export.script_serialization_end_offset + 4  # Skip end marker
    archive.seek(node_export.serial_offset + pins_offset)

    pins_count = archive.read_i32()

    if pins_count < 0:
        raise ParseError(
            f"Invalid pins_count {pins_count} (negative) at node {node_name}",
            context=ErrorContext(
                offset=archive.tell(),
                phase="graph",
                operation="_read_node_pins",
                context_name=node_name,
            ),
        )
    if pins_count > MAX_PINS_PER_NODE:
        raise ParseError(
            f"pins_count {pins_count} exceeds MAX_PINS_PER_NODE {MAX_PINS_PER_NODE} at node {node_name}",
            context=ErrorContext(
                offset=archive.tell(),
                phase="graph",
                operation="_read_node_pins",
                context_name=node_name,
            ),
        )

    pins: List[UEdGraphPin] = []
    for _ in range(pins_count):
        b_null_ptr = archive.read_i32()

        if b_null_ptr != 0:
            archive.read_i32()  # owning_node (unused)
            archive.read_bytes(16)  # pin_guid (unused)
            continue

        header_owning = archive.read_i32()
        header_guid_bytes = archive.read_bytes(16)
        header_pin_id = header_guid_bytes.hex()

        try:
            pin = read_ue_graph_pin(
                archive, name_map, summary, export_map, import_map, linker,
                header_owning_node=header_owning,
                header_pin_id=header_pin_id,
            )
            _local_trace = _get_thread_local().pin_trace_events
            if _local_trace and _local_trace[-1].get("pin_id") == pin.pin_id:
                _local_trace[-1]["node_name"] = node_export.object_name
                _local_trace[-1]["node_guid"] = node_guid
                _local_trace[-1]["node_class"] = _rcn(
                    node_export.class_index, import_map, export_map, linker
                ) or ""
            pins.append(pin)
        except (struct.error, OSError, ValueError, KeyError):
            continue

    return pins

def _read_node_script_serial(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    node_export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"],
    node_name: str,
) -> tuple:
    """读取 node 的 script_serial PropertyTags，返回 (function_reference, event_reference, 局部变量字典, raw_properties)。"""
    function_reference: Optional[FMemberReference] = None
    event_reference: Optional[FMemberReference] = None
    b_override_function: Optional[bool] = None
    b_internal_event: Optional[bool] = None
    custom_function_name: Optional[str] = None
    function_flags: Optional[int] = None
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_guid: str = ""
    node_comment: str = ""
    raw_properties: Dict[str, Any] = {}

    if not node_export.has_script_serialization:
        return (function_reference, event_reference, b_override_function,
                b_internal_event, custom_function_name, function_flags,
                node_pos_x, node_pos_y, node_guid, node_comment, raw_properties)

    script_start = node_export.serial_offset + node_export.script_serialization_start_offset
    script_end = node_export.serial_offset + node_export.script_serialization_end_offset
    archive.seek(script_start)

    # UE5 >= 1011: SerializationControlExtensions
    if summary.file_version_ue5 >= 1011:
        ctrl = archive.read_u8()
        if ctrl & 0x02:
            archive.read_u8()
        # 未知高位处理：停止解析 script_serial 防止偏移错位级联
        if ctrl & ~0x03:
            logger.debug(
                "Node script_serial: 未知 SerializationControlExtensions 位 0x%02X, 跳过后续属性, node=%s",
                ctrl, node_name
            )
            return (function_reference, event_reference, b_override_function,
                    b_internal_event, custom_function_name, function_flags,
                    node_pos_x, node_pos_y, node_guid, node_comment, raw_properties)

    max_property_iterations = max(1000, node_export.script_serialization_size)
    _property_iterations = 0

    while archive.tell() < script_end:
        _property_iterations += 1
        if _property_iterations > max_property_iterations:
            logger.debug(
                "read_ue_graph_node: exceeded max_property_iterations (%d) at node %s, breaking loop",
                max_property_iterations, node_name
            )
            break

        tag_pos = archive.tell()
        try:
            tag = read_property_tag(archive, name_map, tolerant=getattr(archive, '_tolerant', False))
        except ParseError as e:
            logger.debug(
                "read_ue_graph_node: failed to read PropertyTag at pos %d, node=%s: %s",
                tag_pos, node_name, e
            )
            break

        if tag.name == UE_NONE_SENTINEL:
            break

        if tag.name == "FunctionReference" and tag.size > 0:
            function_reference = read_tag_value_bounded(
                archive, tag,
                lambda: _read_member_reference_from_tags(archive, tag, name_map, import_map, export_map, linker)  # noqa: B023 - tag bound at call time
            )
        elif tag.name == "EventReference" and tag.size > 0:
            event_reference = read_tag_value_bounded(
                archive, tag,
                lambda: _read_member_reference_from_tags(archive, tag, name_map, import_map, export_map, linker)  # noqa: B023 - tag bound at call time
            )
        else:
            updates = _read_node_property_tag(
                archive, tag, name_map, import_map, export_map, linker, raw_properties
            )
            if "node_pos_x" in updates:
                node_pos_x = updates["node_pos_x"]
            if "node_pos_y" in updates:
                node_pos_y = updates["node_pos_y"]
            if "node_guid" in updates:
                node_guid = updates["node_guid"]
            if "node_comment" in updates:
                node_comment = updates["node_comment"]
            if "b_override_function" in updates:
                b_override_function = updates["b_override_function"]
            if "b_internal_event" in updates:
                b_internal_event = updates["b_internal_event"]
            if "custom_function_name" in updates:
                custom_function_name = updates["custom_function_name"]
            if "function_flags" in updates:
                function_flags = updates["function_flags"]

    return (function_reference, event_reference, b_override_function,
            b_internal_event, custom_function_name, function_flags,
            node_pos_x, node_pos_y, node_guid, node_comment, raw_properties)

def read_ue_graph_node(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    node_export: ObjectExport,
    linker: Optional["PackageLinker"] = None,
) -> UEdGraphNode:
    """读取 UEdGraphNode 基类字段（含 script_serial PropertyTag 解析）。"""
    archive.seek(node_export.serial_offset)

    node_name = node_export.object_name
    _node_class = _gac(node_export, import_map, export_map, linker)  # noqa: F841 - extracted for clarity

    # 解析 script_serial 中的 tagged properties
    (function_reference, event_reference, b_override_function,
     b_internal_event, custom_function_name, function_flags,
     node_pos_x, node_pos_y, node_guid, node_comment, raw_properties
     ) = _read_node_script_serial(
        archive, name_map, summary, node_export, import_map, export_map, linker, node_name
    )

    # 读取 Pins 数组
    pins = _read_node_pins(
        archive, name_map, summary, export_map, import_map, linker,
        node_export, node_name, node_guid,
    )

    class_name = _rcn(node_export.class_index, import_map, export_map, linker) or ""

    base_node = UEdGraphNode(
        node_guid=node_guid,
        node_pos_x=node_pos_x,
        node_pos_y=node_pos_y,
        node_comment=node_comment,
        pins=pins,
        class_name=class_name,
    )
    base_node._export_object_name = node_export.object_name

    node_refs = {
        'function_reference': function_reference,
        'event_reference': event_reference,
        # K2Node_Event PropertyTag 字段
        'b_override_function': b_override_function,
        'b_internal_event': b_internal_event,
        'custom_function_name': custom_function_name,
        'function_flags': function_flags,
    }

    return create_node_from_archive(
        archive, name_map, summary, export_map, import_map, node_export, base_node,
        raw_properties=raw_properties if raw_properties else None,
        linker=linker,
        node_refs=node_refs,
    )
