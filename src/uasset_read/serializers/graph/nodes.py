"""UEdGraphNode 序列化器 — 节点读取与节点工厂。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import MAX_PINS_PER_NODE
from uasset_read.exceptions import ParseError
from uasset_read.models.core import UEdGraphNode, UEdGraphPin, FMemberReference
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded
from uasset_read.serializers.graph._common import (
    _rcn, _gac, _read_tag_bool, _read_tag_i32, _read_tag_fname,
    read_ftext_with_history, _get_thread_local,
)
from uasset_read.serializers.graph.members import read_fmember_reference
from uasset_read.serializers.graph.pins import read_ue_graph_pin
from uasset_read.serializers.graph.k2_nodes import (
    read_k2node_call_function,
    read_k2node_event,
    read_k2node_knot,
    read_edgraph_node_comment,
    read_k2node_enhanced_input,
    read_k2node_functionentry,
    read_k2node_message,
    read_k2node_call_delegate,
    read_k2node_call_array_function,
    read_k2node_call_parent_function,
    read_k2node_function_result,
    read_k2node_create_widget,
    read_k2node_add_delegate,
    read_k2node_macro_instance,
    read_k2node_assign_delegate,
    read_k2node_get_data_table_row,
    read_k2node_load_asset,
    read_k2node_spawn_actor_from_class,
    _build_trigger_events_from_pins,
)

logger = logging.getLogger(__name__)


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
    """根据 class_name 分派到对应的节点读取函数（D-07/D-08 工厂模式）。"""
    class_name = base_node.class_name

    # 如果 base_node 已经携带 _parse_error 标记，跳过分发保护已有信息
    if isinstance(base_node.node_data, dict) and base_node.node_data.get("_parse_error"):
        return base_node

    # D-11: 使用 PropertyTag 层已解析的 function_reference/event_reference
    if class_name == "K2Node_CallFunction":
        base_node.node_data = read_k2node_call_function(
            archive, name_map, import_map, export_map, linker,
            function_reference=node_refs.get('function_reference') if node_refs else None,
        )
    elif class_name == "K2Node_Event":
        base_node.node_data = read_k2node_event(
            archive, name_map, import_map, export_map, linker,
            event_reference=node_refs.get('event_reference') if node_refs else None,
            b_override_function=node_refs.get('b_override_function') if node_refs else None,
            b_internal_event=node_refs.get('b_internal_event') if node_refs else None,
            custom_function_name=node_refs.get('custom_function_name') if node_refs else None,
            function_flags=node_refs.get('function_flags') if node_refs else None,
        )
    elif class_name == "K2Node_Knot":
        base_node.node_data = read_k2node_knot(archive)
    elif class_name == "EdGraphNode_Comment":
        base_node.node_data = read_edgraph_node_comment(raw_properties)
        if isinstance(base_node.node_data, dict):
            for attr, key in (
                ("comment_color", "comment_color"),
                ("node_width", "node_width"),
                ("node_height", "node_height"),
                ("font_size", "font_size"),
            ):
                value = base_node.node_data.get(key)
                if value is not None:
                    setattr(base_node, attr, value)
    elif class_name == "K2Node_EnhancedInputAction":
        base_node.node_data = read_k2node_enhanced_input(archive, name_map, raw_properties)
        # Populate trigger_events from already-parsed pins
        if isinstance(base_node.node_data, dict):
            base_node.node_data["trigger_events"] = _build_trigger_events_from_pins(base_node.pins)
    elif class_name == "K2Node_FunctionEntry":
        fr = node_refs.get('function_reference') if node_refs else None
        base_node.node_data = read_k2node_functionentry(
            archive, name_map, import_map, export_map, linker,
            function_reference=fr,
            raw_properties=raw_properties,
        )
    elif class_name == "K2Node_Message":
        base_node.node_data = read_k2node_message(
            archive, name_map, import_map, export_map, linker,
        )
    elif class_name == "K2Node_CallDelegate":
        base_node.node_data = read_k2node_call_delegate(archive, name_map)
    elif class_name == "K2Node_CallArrayFunction":
        base_node.node_data = read_k2node_call_array_function(
            archive, name_map, raw_properties=raw_properties,
        )
    elif class_name == "K2Node_CallParentFunction":
        base_node.node_data = read_k2node_call_parent_function(
            archive, name_map, raw_properties=raw_properties,
        )
    elif class_name == "K2Node_FunctionResult":
        base_node.node_data = read_k2node_function_result(
            archive, name_map, raw_properties=raw_properties,
        )
    elif class_name == "K2Node_CreateWidget":
        base_node.node_data = read_k2node_create_widget(
            archive, name_map, raw_properties=raw_properties,
        )
    elif class_name == "K2Node_AddDelegate":
        base_node.node_data = read_k2node_add_delegate(
            archive, name_map, raw_properties=raw_properties,
        )
    elif class_name == "K2Node_MacroInstance":
        base_node.node_data = read_k2node_macro_instance(
            archive, name_map, raw_properties=raw_properties,
        )
    elif class_name == "K2Node_AssignDelegate":
        base_node.node_data = read_k2node_assign_delegate(
            archive, name_map, raw_properties=raw_properties,
        )
    elif class_name == "K2Node_GetDataTableRow":
        base_node.node_data = read_k2node_get_data_table_row(
            archive, name_map, raw_properties=raw_properties,
        )
    elif class_name == "K2Node_LoadAsset":
        base_node.node_data = read_k2node_load_asset(
            archive, name_map, raw_properties=raw_properties,
        )
    elif class_name == "K2Node_SpawnActorFromClass":
        base_node.node_data = read_k2node_spawn_actor_from_class(
            archive, name_map, raw_properties=raw_properties,
        )
    elif raw_properties:
        # 未知类型：保留原始 PropertyTag 元数据用于调试和未来扩展
        base_node.node_data = {"_raw_properties": raw_properties}

    return base_node


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
    node_class = _gac(node_export, import_map, export_map, linker)

    function_reference: Optional[FMemberReference] = None
    event_reference: Optional[FMemberReference] = None
    # K2Node_Event PropertyTag 字段
    b_override_function: Optional[bool] = None
    b_internal_event: Optional[bool] = None
    custom_function_name: Optional[str] = None
    function_flags: Optional[int] = None
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_guid: str = ""
    node_comment: str = ""
    raw_properties: Dict[str, Any] = {}  # 收集未知 PropertyTags（用于未知节点类型）

    # 解析 script_serial 中的 tagged properties
    if node_export.has_script_serialization:
        script_start = node_export.serial_offset + node_export.script_serialization_start_offset
        script_end = node_export.serial_offset + node_export.script_serialization_end_offset
        archive.seek(script_start)

        # UE5 >= 1011: SerializationControlExtensions
        if summary.file_version_ue5 >= 1011:
            ctrl = archive.read_u8()
            if ctrl & 0x02:
                archive.read_u8()

        # 边界保护：防止 script_serialization 不正确导致无限循环
        max_property_iterations = max(1000, node_export.script_serialization_size)
        _property_iterations = 0

        while archive.tell() < script_end:
            _property_iterations += 1
            if _property_iterations > max_property_iterations:
                logger.warning(
                    "read_ue_graph_node: exceeded max_property_iterations (%d) at node %s, breaking loop",
                    max_property_iterations, node_name
                )
                break

            tag_pos = archive.tell()
            try:
                tag = read_property_tag(archive, name_map, tolerant=getattr(archive, '_tolerant', False))
            except ParseError as e:
                logger.warning(
                    "read_ue_graph_node: failed to read PropertyTag at pos %d, node=%s: %s",
                    tag_pos, node_name, e
                )
                break

            if tag.name == "None":
                break

            if tag.name == "FunctionReference" and tag.size > 0:
                def _read_function_reference() -> FMemberReference:
                    value_end = tag.value_end_offset or (archive.tell() + tag.size)
                    mp_idx = 0
                    m_name = ""
                    m_guid = ""
                    m_self = False

                    while archive.tell() < value_end:
                        inner = read_property_tag(archive, name_map)
                        if inner.name == "None":
                            break
                        if inner.value_end_offset is not None and inner.value_end_offset > value_end:
                            raise ParseError(
                                f"FunctionReference field '{inner.name}' exceeds struct boundary"
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

                function_reference = read_tag_value_bounded(archive, tag, _read_function_reference)
            elif tag.name == "EventReference" and tag.size > 0:
                def _read_event_reference() -> FMemberReference:
                    value_end = tag.value_end_offset or (archive.tell() + tag.size)
                    mp_idx = 0
                    m_name = ""
                    m_guid = ""
                    m_self = False

                    while archive.tell() < value_end:
                        inner = read_property_tag(archive, name_map)
                        if inner.name == "None":
                            break
                        if inner.value_end_offset is not None and inner.value_end_offset > value_end:
                            raise ParseError(
                                f"EventReference field '{inner.name}' exceeds struct boundary"
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

                event_reference = read_tag_value_bounded(archive, tag, _read_event_reference)
            # K2Node_Event PropertyTag 字段使用 helper functions
            # 注意：这些字段会在后面的 elif 分支（使用 helper functions）处理
            # 这里只是占位注释，实际处理在 lines 1859-1872
            elif tag.name == "NodePosX":
                node_pos_x = _read_tag_i32(archive, tag)
            elif tag.name == "NodePosY":
                node_pos_y = _read_tag_i32(archive, tag)
            elif tag.name == "NodeGuid" and tag.size > 0:
                node_guid = archive.read_bytes(16).hex()
                if archive.tell() < tag.value_end_offset:
                    archive.seek(tag.value_end_offset)
            elif tag.name == "NodeComment" and tag.size > 0:
                node_comment = archive.read_fstring()
                if archive.tell() < tag.value_end_offset:
                    archive.seek(tag.value_end_offset)
            elif tag.name == "InputAction" and tag.size > 0:
                pkg_idx = archive.read_i32()
                input_action_path = (
                    _rcn(PackageIndex(pkg_idx), import_map, export_map, linker)
                    if pkg_idx != 0 else ""
                )
                raw_properties[tag.name] = input_action_path
                # 保留短名提取
                raw_properties["InputActionShortName"] = (
                    input_action_path.split(".")[-1].split("'")[0]
                    if input_action_path else ""
                )
                raw_properties["InputActionPackageIndex"] = pkg_idx
                if archive.tell() < tag.value_end_offset:
                    archive.seek(tag.value_end_offset)
            elif tag.name == "CommentColor" and tag.size >= 16:
                raw_properties[tag.name] = (
                    archive.read_f32(),
                    archive.read_f32(),
                    archive.read_f32(),
                    archive.read_f32(),
                )
                if archive.tell() < tag.value_end_offset:
                    archive.seek(tag.value_end_offset)
            elif tag.name in ("NodeWidth", "NodeHeight", "FontSize") and tag.size > 0:
                raw_properties[tag.name] = _read_tag_i32(archive, tag)
            elif tag.name == "bCommentBubbleVisible_InDetailsPanel":
                raw_properties[tag.name] = _read_tag_bool(archive, tag)
            elif tag.name == "CommentDepth" and tag.size > 0:
                raw_properties[tag.name] = _read_tag_i32(archive, tag)
            elif tag.name == "ExtraFlags" and tag.size > 0:
                raw_properties[tag.name] = _read_tag_i32(archive, tag)
            # 新增节点字段收集
            elif tag.name == "AdvancedPinDisplay" and tag.size > 0:
                raw_val = _read_tag_i32(archive, tag)
                raw_properties[tag.name] = raw_val
                # 格式化枚举名映射（EAdvancedPinDisplay）
                enum_map = {0: "Default", 1: "Hidden", 2: "Shown"}
                raw_properties["AdvancedPinDisplayFormatted"] = enum_map.get(raw_val, f"Unknown({raw_val})")
            elif tag.name == "bOverrideFunction":
                b_override_function = _read_tag_bool(archive, tag)
                raw_properties[tag.name] = b_override_function
            elif tag.name == "bInternalEvent":
                b_internal_event = _read_tag_bool(archive, tag)
                raw_properties[tag.name] = b_internal_event
            elif tag.name == "bIsEditable":
                raw_properties[tag.name] = _read_tag_bool(archive, tag)
            elif tag.name == "CustomFunctionName":
                custom_function_name = _read_tag_fname(archive, tag, name_map)
                raw_properties[tag.name] = custom_function_name
            elif tag.name == "FunctionFlags" and tag.size > 0:
                function_flags = _read_tag_i32(archive, tag)
                raw_properties[tag.name] = function_flags
            elif tag.name == "CustomGeneratedFunctionName":
                raw_properties[tag.name] = _read_tag_fname(archive, tag, name_map)
            elif tag.name == "MoveMode" and tag.size > 0:
                # MoveMode 通常为 byte/int
                raw_val = archive.read_u8() if tag.size >= 1 else 0
                raw_properties[tag.name] = raw_val
                if archive.tell() < tag.value_end_offset:
                    archive.seek(tag.value_end_offset)
            elif tag.name == "NodeDetails" and tag.size > 0:
                # NodeDetails 为 FText，尝试读取预览
                try:
                    flags = archive.read_i32()
                    history_type_raw = archive.read_u8()
                    history_type = history_type_raw - 256 if history_type_raw >= 128 else history_type_raw
                    read_ftext_with_history(archive, history_type, tolerant=True)
                except Exception:
                    pass
                if archive.tell() < tag.value_end_offset:
                    archive.seek(tag.value_end_offset)
                raw_properties[tag.name] = {"size": tag.size, "type": "FText"}
            elif tag.size > 0:
                # 收集未知 PropertyTag（用于未知节点类型调试和未来扩展）
                value_start = archive.tell()
                raw_properties[tag.name] = {"size": tag.size, "offset": value_start}
                archive.seek(tag.value_end_offset)

    # 读取 Pins 数组
    # D-12: UE5 UEdGraphNode Pins format:
    #   - End marker (4 bytes, value=0) after script_serial
    #   - pins_count (i32)
    #   - TArray<UEdGraphPin> elements with header (b_null_ptr + owning_node + pin_guid)
    pins_offset = node_export.script_serialization_end_offset + 4  # Skip end marker
    archive.seek(node_export.serial_offset + pins_offset)

    pins_count = archive.read_i32()

    if pins_count < 0:
        raise ParseError(f"Invalid pins_count {pins_count} (negative) at node {node_name}")
    if pins_count > MAX_PINS_PER_NODE:
        raise ParseError(f"pins_count {pins_count} exceeds MAX_PINS_PER_NODE {MAX_PINS_PER_NODE} at node {node_name}")

    pins: List[UEdGraphPin] = []
    for _ in range(pins_count):
        # D-12: UE5 Pin array uses PinReference format:
        #   Header: b_null_ptr + owning_node + pin_guid
        #   Body: Complete UEdGraphPin (duplicates owning_node + pin_guid, then PinName + ...)
        b_null_ptr = archive.read_i32()

        if b_null_ptr != 0:
            # NULL pin reference: skip remaining header (owning_node + pin_guid)
            archive.read_i32()  # owning_node (unused)
            archive.read_bytes(16)  # pin_guid (unused)
            continue

        # Read external header: owning_node and pin_guid
        header_owning = archive.read_i32()
        header_guid_bytes = archive.read_bytes(16)
        header_pin_id = header_guid_bytes.hex().upper()

        try:
            # D-12: Pass header values to skip internal duplicates
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
        except Exception:
            continue

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
