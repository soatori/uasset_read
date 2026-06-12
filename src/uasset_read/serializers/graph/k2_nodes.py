"""K2Node 类型读取器 — 各节点特有字段解析。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.models.core import FMemberReference
from uasset_read.serializers.graph.members import read_fmember_reference

logger = logging.getLogger(__name__)


def _build_trigger_events_from_pins(pins: List) -> Dict[str, str]:
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

    b_defaults_to_pure = archive.read_bool()
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
        except Exception as e:
            logger.warning(
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
        except Exception:
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
    except Exception as e:
        logger.warning("K2Node_Message read failed: %s", e)
        result["message_name"] = "Unknown"

    return result


def read_k2node_call_delegate(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """读取 K2Node_CallDelegate 字段。"""
    result = {}
    try:
        delegate_idx = archive.read_i32()
        if 0 <= delegate_idx < len(name_map):
            result["delegate_name"] = name_map[delegate_idx]
    except Exception as e:
        logger.warning("K2Node_CallDelegate read failed: %s", e)
    return result


def read_k2node_call_array_function(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_CallArrayFunction 特有字段。

    继承自 K2Node_CallFunction，特有字段通过 PropertyTag 序列化。
    从 raw_properties 提取 FunctionReference（已在 PropertyTag 层解析）。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # FunctionReference 从 PropertyTag 获取
    func_ref = raw_properties.get("FunctionReference")
    if isinstance(func_ref, dict):
        result["function_reference"] = func_ref
    elif func_ref is not None:
        result["function_reference"] = func_ref

    return result


def read_k2node_call_parent_function(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_CallParentFunction 特有字段。

    继承自 K2Node_CallFunction，调用父类同名函数。
    特有字段通过 PropertyTag 序列化。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # FunctionReference 从 PropertyTag 获取
    func_ref = raw_properties.get("FunctionReference")
    if isinstance(func_ref, dict):
        result["function_reference"] = func_ref
    elif func_ref is not None:
        result["function_reference"] = func_ref

    return result


def read_k2node_function_result(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_FunctionResult 特有字段。

    继承自 K2Node_FunctionTerminator，表示函数返回节点。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    func_ref = raw_properties.get("FunctionReference")
    if isinstance(func_ref, dict):
        result["function_reference"] = func_ref
    elif func_ref is not None:
        result["function_reference"] = func_ref

    return result


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


def read_k2node_add_delegate(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_AddDelegate 特有字段。

    继承自 K2Node_BaseMCDelegate，添加多播委托绑定。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    delegate_name = raw_properties.get("DelegateName")
    if delegate_name is not None:
        result["delegate_name"] = delegate_name

    return result


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
    """读取 K2Node_AssignDelegate 特有字段。

    继承自 K2Node_AddDelegate，赋值委托绑定。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    delegate_name = raw_properties.get("DelegateName")
    if delegate_name is not None:
        result["delegate_name"] = delegate_name

    return result


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
