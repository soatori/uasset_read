"""蓝图图二进制序列化器 — FEdGraphPinType, UEdGraphPin, UEdGraphNode, UEdGraph 读取函数。

等价迁移 uasset_read.py L3191-4679。
Phase 31: 蓝图图解析模块 (per MOD-09)。
"""
from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport

from uasset_read.constants import (
    MAX_PINS_PER_NODE, MAX_NODES_PER_GRAPH, MAX_LINKEDTO_PER_PIN,
    START_EVENT_TYPES, CONTROL_FLOW_NODES, BRANCH_TYPE_MAP,
    FFRAMEWORK_OBJECT_VERSION_GUID, FUE5_MAINSTREAM_VERSION_GUID, FRELEASE_OBJECT_VERSION_GUID,
    FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE, FFRAMEWORK_VERSION_PINS_STORE_FNAME,
    FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX,
    FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER,
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
    FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION,
)

logger = logging.getLogger(__name__)
from uasset_read.exceptions import ParseError
from uasset_read.serializers.object_resources import resolve_class_name, get_asset_class, PackageIndex
from uasset_read.serializers.property_tags import read_property_tag
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType, FMemberReference
from uasset_read.models.node_types import K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment, K2NodeEnhancedInputAction


# ============================================================================
# FEdGraphPinType 读取
# ============================================================================

def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> FEdGraphPinType:
    """解析 FEdGraphPinType（两种序列化模式）。

    自定义序列化：UE4 >= 324
    默认反射序列化：UE5 资产（UE4 < 324）
    """
    pin_type = FEdGraphPinType()

    framework_version = summary.get_custom_version(FFRAMEWORK_OBJECT_VERSION_GUID, 0)
    release_version = summary.get_custom_version(FRELEASE_OBJECT_VERSION_GUID, 0)
    ue4_version = summary.file_version_ue4

    VER_UE4_EDGRAPHPINTYPE_SERIALIZATION = 324
    use_custom_serialization = ue4_version >= VER_UE4_EDGRAPHPINTYPE_SERIALIZATION

    if not use_custom_serialization:
        # 默认反射序列化（UE5 资产）— EdGraphPin.h L76-133
        pin_type.pin_category = archive.read_name(name_map)
        pin_type.pin_subcategory = archive.read_name(name_map)
        pin_type.pin_subcategory_object = archive.read_i32()
        # PinSubCategoryMemberReference: FSimpleMemberReference
        archive.read_i32()       # MemberParent
        archive.read_name(name_map)  # MemberName
        archive.read_bytes(16)   # MemberGuid
        # PinValueType: FEdGraphTerminalType
        archive.read_name(name_map)  # TerminalCategory
        archive.read_name(name_map)  # TerminalSubCategory
        archive.read_i32()           # TerminalSubCategoryObject
        # ContainerType
        pin_type.container_type = archive.read_u8()
        # Bit flags (bIsArray_DEPRECATED + flags as uint8:1)
        flags_byte = archive.read_u8()
        pin_type.is_reference = (flags_byte & 0x04) != 0
        pin_type.is_const = (flags_byte & 0x08) != 0
        pin_type.is_weak_pointer = (flags_byte & 0x10) != 0
        pin_type.is_uobject_wrapper = (flags_byte & 0x20) != 0
    else:
        # 自定义序列化（UE4 >= 324）— EdGraphPin.cpp L163-346
        use_fname_format = framework_version >= FFRAMEWORK_VERSION_PINS_STORE_FNAME or summary.file_version_ue5 > 0

        # PinCategory / PinSubCategory
        if use_fname_format:
            pin_type.pin_category = archive.read_name(name_map)
            pin_type.pin_subcategory = archive.read_name(name_map)
        else:
            pin_type.pin_category = archive.read_fstring()
            pin_type.pin_subcategory = archive.read_fstring()

        # PinSubCategoryObject
        pin_type.pin_subcategory_object = archive.read_i32()

        # ContainerType (version dependent)
        use_modern_container = framework_version >= FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE or summary.file_version_ue5 > 0
        if use_modern_container:
            pin_type.container_type = archive.read_u8()
            if pin_type.container_type == 3:  # Map
                archive.read_name(name_map)  # TerminalCategory
                archive.read_name(name_map)  # TerminalSubCategory
                archive.read_i32()           # TerminalSubCategoryObject
        else:
            b_is_map = archive.read_bool()
            b_is_set = archive.read_bool()
            b_is_array = archive.read_bool()
            if b_is_map:
                pin_type.container_type = 3
            elif b_is_set:
                pin_type.container_type = 2
            elif b_is_array:
                pin_type.container_type = 1
            else:
                pin_type.container_type = 0

        # bIsReference / bIsWeakPointer
        pin_type.is_reference = archive.read_bool_ue5() if summary.file_version_ue5 > 0 else archive.read_bool()
        pin_type.is_weak_pointer = archive.read_bool_ue5() if summary.file_version_ue5 > 0 else archive.read_bool()

        # FSimpleMemberReference (version dependent)
        VER_UE4_MEMBERREFERENCE_IN_PINTYPE = 382
        if ue4_version >= VER_UE4_MEMBERREFERENCE_IN_PINTYPE:
            archive.read_i32()       # MemberParent
            archive.read_name(name_map)  # MemberName
            archive.read_bytes(16)   # MemberGuid

        # bIsConst (version dependent)
        VER_UE4_SERIALIZE_PINTYPE_CONST = 366
        if ue4_version >= VER_UE4_SERIALIZE_PINTYPE_CONST:
            pin_type.is_const = archive.read_bool_ue5() if summary.file_version_ue5 > 0 else archive.read_bool()
        else:
            pin_type.is_const = False

        # bIsUObjectWrapper (version dependent, +1 Byte Abweichung Quelle D1)
        # C++: if Ar.CustomVer(FReleaseObjectVersion::GUID) >= PinTypeIncludesUObjectWrapperFlag
        # Fallback: UE5 Assets haben immer ReleaseObjectVersion >= 10, auch wenn GUID nicht in custom version table
        if release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER or summary.file_version_ue5 > 0:
            pin_type.is_uobject_wrapper = archive.read_bool_ue5() if summary.file_version_ue5 > 0 else archive.read_bool()
        else:
            pin_type.is_uobject_wrapper = False

    return pin_type


# ============================================================================
# FText 读取（UE5 多 history_type 支持）
# ============================================================================

def _read_fstring_safe(archive: FArchive, max_length: int = 10_000) -> str:
    """读取 FString，对异常长度进行容错处理。

    如果长度不合理（超过 max_length），尝试读取为 0 字节空字符串。
    """
    length = archive.read_i32()
    if length == 0:
        return ""
    if abs(length) > max_length:
        # 长度异常，回退并返回空字符串
        archive.seek(archive.tell() - 4)
        return ""
    if length < 0:
        utf16_len = -length * 2
        if utf16_len > max_length * 2:
            archive.seek(archive.tell() - 4)
            return ""
        data = archive.read(utf16_len)
        return data.decode('utf-16', errors='replace').rstrip('\x00')
    data = archive.read(length)
    return data.decode('utf-8', errors='replace').rstrip('\x00')


def _read_ftext_fstring(archive: FArchive) -> str:
    """读取 FText 内部的 FString，对异常长度不回退（已消费 i32 长度字段）。

    与 _read_fstring_safe 的关键区别：长度异常时不回退 seek，
    直接返回空字符串，确保 FText 内部每个 FString 即使长度异常，
    文件位置也不会错位。
    """
    length = archive.read_i32()
    if length == 0:
        return ""
    if abs(length) > 10_000:
        # 异常长度，不回退（已消费 i32），返回空字符串
        return ""
    if length < 0:
        data = archive.read(-length * 2)
        return data.decode('utf-16', errors='replace').rstrip('\x00')
    data = archive.read(length)
    return data.decode('utf-8', errors='replace').rstrip('\x00')


def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
    ue5_mode: bool = False,
) -> tuple[str, int]:
    """读取 FText，返回 (值, 消耗字节数)。

    history_type:
    - 0xFF (-1 as unsigned): None（无历史）
    - 0 (Base): Namespace + Key + SourceString
    - 1-254: Custom（最多 5 个 FString 历史）

    Args:
        archive: FArchive 实例
        history_type: FText 历史类型
        tolerant: 是否启用容错模式
        ue5_mode: 是否为 UE5 资产（影响 b_has_culture 的 bool 读取大小）

    容错模式下，对异常长度返回空字符串而非抛出异常。
    """
    consumed = 0
    start_pos = archive.tell()

    try:
        if history_type == 0xFF:
            # None 类型：仅 flags + 可选 culture
            b_has_culture = archive.read_bool_ue5() if ue5_mode else archive.read_bool()
            if b_has_culture:
                culture_start = archive.tell()
                try:
                    archive.read_fstring()  # culture
                except Exception:
                    if tolerant:
                        archive.seek(culture_start)
                    else:
                        raise
        elif history_type == 0:
            # Base 类型：3 个 FString
            for _ in range(3):
                fstring_start = archive.tell()
                try:
                    _read_fstring_safe(archive)
                except Exception:
                    if tolerant:
                        archive.seek(fstring_start)
                        break
                    else:
                        raise
        else:
            # Custom 类型：history_type 1-254
            # UE5 FText EditorOnly 格式可能包含固定 8 字节而非标准 FString 序列
            # 尝试读取第一个 FString，如果位置未前进则跳过 8 字节
            fstring_start = archive.tell()
            _read_fstring_safe(archive)
            after_first = archive.tell()

            if after_first == fstring_start:
                # _read_fstring_safe 因长度异常而回退 — UE5 EditorOnly 格式
                # 跳过固定 8 字节神秘数据
                archive.seek(fstring_start + 8)
            else:
                # 成功读取一个 FString，继续尝试剩余 4 个
                for _ in range(4):
                    next_start = archive.tell()
                    _read_fstring_safe(archive)
                    if archive.tell() == next_start:
                        # 长度异常，停止
                        archive.seek(next_start)
                        break
    except Exception as e:
        if tolerant:
            logger.debug("FText tolerant mode: history_type=%s, error=%s", history_type, e)
        else:
            raise ParseError(f"Failed to read FText with history_type={history_type}: {e}")

    consumed = archive.tell() - start_pos
    return "", consumed


# ============================================================================
# Pin 引用辅助函数
# ============================================================================

def read_pin_reference(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport]
) -> Optional[dict]:
    """读取单个 Pin 引用（SerializePin 格式）。"""
    b_null_ptr = archive.read_i32()
    if b_null_ptr != 0:
        return None

    owning_node_index = archive.read_i32()
    pin_guid_bytes = archive.read_bytes(16)
    pin_guid = pin_guid_bytes.hex().upper()

    # 解析 owning node 名称
    owning_node_name: Optional[str] = None
    if owning_node_index > 0:
        node_idx = owning_node_index - 1
        if node_idx < len(export_map):
            owning_node_name = export_map[node_idx].object_name
    elif owning_node_index < 0:
        import_idx = -owning_node_index - 1
        if import_idx < len(import_map):
            owning_node_name = import_map[import_idx].object_name

    return {"owning_node": owning_node_name, "pin_guid": pin_guid}


def read_pin_array(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport]
) -> List[dict]:
    """读取 Pin 引用数组（SerializePinArray 格式）。"""
    array_count = archive.read_i32()

    if array_count < 0:
        raise ParseError(f"Invalid pin array count: {array_count} (negative)")
    if array_count > MAX_LINKEDTO_PER_PIN:
        raise ParseError(
            f"Pin array count {array_count} exceeds MAX_LINKEDTO_PER_PIN {MAX_LINKEDTO_PER_PIN}"
        )

    pins: List[dict] = []
    for _ in range(array_count):
        pin_ref = read_pin_reference(archive, name_map, export_map, import_map)
        if pin_ref is not None:
            pins.append(pin_ref)
    return pins


# ============================================================================
# UEdGraphPin 读取
# ============================================================================

def read_ue_graph_pin(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport]
) -> UEdGraphPin:
    """读取 UEdGraphPin 完整序列化格式（EdGraphPin.cpp L1838-1964）。"""
    framework_version = summary.get_custom_version(FFRAMEWORK_OBJECT_VERSION_GUID, 0)
    mainstream_version = summary.get_custom_version(FUE5_MAINSTREAM_VERSION_GUID, 0)
    use_fname_format = framework_version >= FFRAMEWORK_VERSION_PINS_STORE_FNAME or summary.file_version_ue5 > 0

    pin_start_pos = archive.tell()

    # 1. OwningNode
    owning_node_index = archive.read_i32()

    # 2. PinId (FGuid 16 bytes)
    pin_id_bytes = archive.read_bytes(16)
    pin_id = pin_id_bytes.hex().upper()

    # 3. PinName (version dependent)
    if use_fname_format:
        pin_name = archive.read_name(name_map)
    else:
        pin_name = archive.read_fstring()

    # 4. PinFriendlyName (FText) — EditorOnly, try/except + seek-back
    ftext_start_pos = archive.tell()
    try:
        flags = archive.read_i32()
        history_type = archive.read_u8()
        read_ftext_with_history(archive, history_type, tolerant=True, ue5_mode=(summary.file_version_ue5 > 0))
    except Exception:
        archive.seek(ftext_start_pos)

    # 5. SourceIndex (version dependent)
    source_index = None
    # UE5 always serializes SourceIndex; the mainstream_version threshold check
    # is unreliable (mainstream_version=0 for UE5.5 assets)
    if mainstream_version >= FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX or summary.file_version_ue5 > 0:
        source_index = archive.read_i32()
    else:
        start_pos = archive.tell()
        try:
            test_source = archive.read_i32()
            if -100 <= test_source <= 1000000:
                source_index = test_source
            else:
                archive.seek(start_pos)
        except Exception:
            archive.seek(start_pos)

    # 6. PinToolTip
    # 6. PinToolTip — UE5: len=-1 means empty with no data bytes
    if summary.file_version_ue5 > 0:
        _tt_len = archive.read_i32()
        if _tt_len == -1:
            pin_tooltip = ""
        elif _tt_len == 0:
            pin_tooltip = ""
        elif _tt_len < 0:
            pin_tooltip = archive.read(-_tt_len * 2).decode('utf-16', errors='replace').rstrip('\x00')
        else:
            pin_tooltip = archive.read(_tt_len).decode('utf-8', errors='replace').rstrip('\x00')
    else:
        pin_tooltip = archive.read_fstring()

    # 7. Direction — u8 for both UE4 and UE5
    direction = archive.read_u8()

    # 8. PinType
    pin_type = read_ed_graph_pin_type(archive, name_map, summary)

    # 9-10. DefaultValue strings (容错)
    try:
        default_value = archive.read_fstring()
    except Exception:
        default_value = ""

    try:
        autogenerated_default_value = archive.read_fstring()
    except Exception:
        autogenerated_default_value = ""

    # 11. DefaultObject (FPackageIndex)
    default_object = archive.read_i32()

    # 12. DefaultTextValue (FText) — NICHT FString!
    # UE5 C++: Ar << DefaultTextValue; (EdGraphPin.cpp L1876)
    # FText Serialisierung: flags(i32,4B) + history_type(u8,1B) + body(variable)
    # Siehe read_ftext_with_history() fuer history_type Verarbeitung
    try:
        _dtv_flags = archive.read_i32()
        _dtv_history = archive.read_u8()
        _dtv_value, _dtv_consumed = read_ftext_with_history(
            archive, _dtv_history,
            tolerant=True,
            ue5_mode=(summary.file_version_ue5 > 0)
        )
    except Exception:
        # Extrem tolerant: Falls FText-Lesen fehlschlaegt, DefaultTextValue ignorieren
        pass

    # 13. LinkedTo array
    linkedto_start = archive.tell()
    try:
        linked_to = read_pin_array(archive, name_map, export_map, import_map)
    except Exception:
        # 不尝试恢复 — 异常可能由数据损坏导致，继续解析可能导致位置不一致
        # 返回空数组，让调用者处理位置不一致问题
        linked_to = []

    # 14. SubPins array
    subpins_start = archive.tell()
    try:
        sub_pins = read_pin_array(archive, name_map, export_map, import_map)
    except Exception:
        # 同上，不尝试恢复
        sub_pins = []

    # 15. ParentPin — UE5: always 24 bytes (b_null + owning + guid)
    if summary.file_version_ue5 > 0:
        _pp_null = archive.read_i32()
        _pp_owning = archive.read_i32()
        _pp_guid = archive.read_bytes(16).hex().upper() if _pp_null == 0 else None
        parent_pin = {"owning_node": None, "pin_guid": _pp_guid} if _pp_null == 0 else None
    else:
        parent_pin = read_pin_reference(archive, name_map, export_map, import_map)

    # 16. ReferencePassThroughConnection — UE5: always 24 bytes
    if summary.file_version_ue5 > 0:
        _ref_null = archive.read_i32()
        _ref_owning = archive.read_i32()
        _ref_guid = archive.read_bytes(16).hex().upper() if _ref_null == 0 else None
        ref_pass_through = {"owning_node": None, "pin_guid": _ref_guid} if _ref_null == 0 else None
    else:
        ref_pass_through = read_pin_reference(archive, name_map, export_map, import_map)

    # 17. PersistentGuid (EditorOnly)
    try:
        persistent_guid_bytes = archive.read_bytes(16)
        persistent_guid = persistent_guid_bytes.hex().upper()
    except Exception:
        persistent_guid = None

    # 18. BitField (EditorOnly) — uint32 in both UE4 and UE5 (EdGraphPin.cpp L1902)
    hidden = False
    not_connectable = False
    advanced_view = False
    orphaned_pin = False
    try:
        bitfield = archive.read_u32()
        hidden = bool(bitfield & (1 << 0))
        not_connectable = bool(bitfield & (1 << 1))
        advanced_view = bool(bitfield & (1 << 4))
        orphaned_pin = bool(bitfield & (1 << 5))
    except Exception:
        pass

    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        pin_tooltip=pin_tooltip,
        direction=direction,
        pin_type=pin_type,
        default_value=default_value,
        auto_default_value=autogenerated_default_value,
        default_object=default_object,
        linked_to_raw=linked_to,
        sub_pins=sub_pins,
        parent_pin=parent_pin,
        owning_node_index=owning_node_index,
        source_index=source_index,
        persistent_guid=persistent_guid,
        hidden=hidden,
        not_connectable=not_connectable,
        advanced_view=advanced_view,
        orphaned_pin=orphaned_pin,
    )


# ============================================================================
# FMemberReference 读取
# ============================================================================

def read_fmember_reference(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> FMemberReference:
    """读取 FMemberReference（MemberReference.h L74-95）。"""
    member_parent_index = archive.read_i32()
    member_parent: Optional[str] = None
    if member_parent_index != 0:
        member_parent = resolve_class_name(
            PackageIndex(member_parent_index), import_map, export_map
        )

    member_scope = archive.read_fstring()
    member_name = archive.read_name(name_map)
    member_guid = archive.read_bytes(16).hex()
    b_self_context = archive.read_bool()
    _b_was_deprecated = archive.read_bool()

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
    export_map: List[ObjectExport]
) -> Dict[str, Any]:
    """读取 K2Node_CallFunction 特有字段，返回字典（作为 node_data）。"""
    function_reference = read_fmember_reference(archive, name_map, import_map, export_map)
    b_defaults_to_pure = archive.read_bool()
    return {
        "function_reference": function_reference,
        "b_defaults_to_pure": b_defaults_to_pure,
    }


def read_k2node_event(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Dict[str, Any]:
    """读取 K2Node_Event 特有字段，返回字典（作为 node_data）。"""
    event_reference = read_fmember_reference(archive, name_map, import_map, export_map)
    b_override_function = archive.read_bool()
    return {
        "event_reference": event_reference,
        "b_override_function": b_override_function,
    }


def read_k2node_knot(archive: FArchive) -> Dict[str, Any]:
    """K2Node_Knot 无额外字段。"""
    return {}


def read_edgraph_node_comment(archive: FArchive) -> Dict[str, Any]:
    """读取 EdGraphNode_Comment 特有字段，返回字典（作为 node_data）。"""
    r = struct.unpack('<f', archive.read(4))[0]
    g = struct.unpack('<f', archive.read(4))[0]
    b = struct.unpack('<f', archive.read(4))[0]
    a = struct.unpack('<f', archive.read(4))[0]
    comment_color = (r, g, b, a)

    node_width = archive.read_i32()
    node_height = archive.read_i32()
    font_size = archive.read_i32()

    return {
        "comment_color": comment_color,
        "node_width": node_width,
        "node_height": node_height,
        "font_size": font_size,
    }


def read_k2node_enhanced_input(
    archive: FArchive,
    name_map: List[str]
) -> Dict[str, Any]:
    """读取 K2Node_EnhancedInputAction 特有字段，返回字典（作为 node_data）。"""
    input_action_path = archive.read_fstring()
    return {
        "input_action_path": input_action_path,
    }


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
) -> UEdGraphNode:
    """根据 class_name 分派到对应的节点读取函数（D-07/D-08 工厂模式）。"""
    class_name = base_node.class_name

    # 如果 base_node 已经携带 _parse_error 标记，跳过分发保护已有信息
    if isinstance(base_node.node_data, dict) and base_node.node_data.get("_parse_error"):
        return base_node

    if class_name == "K2Node_CallFunction":
        base_node.node_data = read_k2node_call_function(
            archive, name_map, import_map, export_map
        )
    elif class_name == "K2Node_Event":
        base_node.node_data = read_k2node_event(
            archive, name_map, import_map, export_map
        )
    elif class_name == "K2Node_Knot":
        base_node.node_data = read_k2node_knot(archive)
    elif class_name == "EdGraphNode_Comment":
        base_node.node_data = read_edgraph_node_comment(archive)
    elif class_name == "K2Node_EnhancedInputAction":
        base_node.node_data = read_k2node_enhanced_input(archive, name_map)
    elif raw_properties:
        # 未知类型：保留原始 PropertyTag 元数据用于调试和未来扩展
        base_node.node_data = {"_raw_properties": raw_properties}

    return base_node


# ============================================================================
# UEdGraphNode 读取
# ============================================================================

def read_ue_graph_node(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    node_export: ObjectExport,
) -> UEdGraphNode:
    """读取 UEdGraphNode 基类字段（含 script_serial PropertyTag 解析）。"""
    archive.seek(node_export.serial_offset)

    node_name = node_export.object_name
    node_class = get_asset_class(node_export, import_map, export_map)

    function_reference: Optional[FMemberReference] = None
    event_reference: Optional[FMemberReference] = None
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_guid: str = ""
    node_comment: str = ""
    raw_properties: Dict[str, Any] = {}  # 收集未知 PropertyTags（用于未知节点类型）

    # 解析 script_serial 中的 tagged properties
    if node_export.script_serial_size > 0:
        script_start = node_export.serial_offset + node_export.script_serial_offset
        script_end = script_start + node_export.script_serial_size
        archive.seek(script_start)

        # UE5 >= 1011: SerializationControlExtensions
        if summary.file_version_ue5 >= 1011:
            ctrl = archive.read_u8()
            if ctrl & 0x02:
                archive.read_u8()

        while archive.tell() < script_end:
            tag = read_property_tag(archive, name_map, summary.legacy_file_version, summary.file_version_ue5, tolerant=archive._tolerant)
            if tag.name == "None":
                break

            if tag.name == "FunctionReference" and tag.size > 0:
                value_end = archive.tell() + tag.size
                mp_idx = 0
                m_scope = ""
                m_name = ""
                m_guid = ""
                m_self = False

                while archive.tell() < value_end:
                    inner = read_property_tag(archive, name_map, summary.legacy_file_version, summary.file_version_ue5)
                    if inner.name == "None":
                        break
                    if inner.name == "MemberParent" and inner.size > 0:
                        mp_idx = archive.read_i32()
                    elif inner.name == "MemberScope" and inner.size > 0:
                        m_scope = archive.read_fstring()
                    elif inner.name == "MemberName":
                        m_name = archive.read_name(name_map)
                    elif inner.name == "MemberGuid" and inner.size > 0:
                        m_guid = archive.read_bytes(16).hex()
                    elif inner.name == "bSelfContext":
                        if inner.size > 0:
                            m_self = archive.read_i32() != 0
                        else:
                            m_self = inner.bool_val != 0
                    elif inner.name == "bWasDeprecated" and inner.size > 0:
                        archive.read_i32()
                    elif inner.size > 0:
                        archive.seek(archive.tell() + inner.size)

                function_reference = FMemberReference(
                    member_parent=resolve_class_name(PackageIndex(mp_idx), import_map, export_map) if mp_idx != 0 else None,
                    member_name=m_name,
                    member_guid=m_guid,
                    b_self_context=m_self,
                )
            elif tag.name == "EventReference" and tag.size > 0:
                value_end = archive.tell() + tag.size
                mp_idx = 0
                m_name = ""
                m_guid = ""
                m_self = False

                while archive.tell() < value_end:
                    inner = read_property_tag(archive, name_map, summary.legacy_file_version, summary.file_version_ue5)
                    if inner.name == "None":
                        break
                    if inner.name == "MemberParent" and inner.size > 0:
                        mp_idx = archive.read_i32()
                    elif inner.name == "MemberScope" and inner.size > 0:
                        archive.read_fstring()
                    elif inner.name == "MemberName":
                        m_name = archive.read_name(name_map)
                    elif inner.name == "MemberGuid" and inner.size > 0:
                        m_guid = archive.read_bytes(16).hex()
                    elif inner.name == "bSelfContext":
                        if inner.size > 0:
                            m_self = archive.read_i32() != 0
                        else:
                            m_self = inner.bool_val != 0
                    elif inner.name == "bWasDeprecated" and inner.size > 0:
                        archive.read_i32()
                    elif inner.size > 0:
                        archive.seek(archive.tell() + inner.size)

                event_reference = FMemberReference(
                    member_parent=resolve_class_name(PackageIndex(mp_idx), import_map, export_map) if mp_idx != 0 else None,
                    member_name=m_name,
                    member_guid=m_guid,
                    b_self_context=m_self,
                )
            elif tag.name == "NodePosX":
                node_pos_x = archive.read_i32()
            elif tag.name == "NodePosY":
                node_pos_y = archive.read_i32()
            elif tag.name == "NodeGuid" and tag.size > 0:
                node_guid = archive.read_bytes(16).hex()
            elif tag.name == "NodeComment" and tag.size > 0:
                node_comment = archive.read_fstring()
            elif tag.size > 0:
                # 收集未知 PropertyTag（用于未知节点类型调试和未来扩展）
                value_start = archive.tell()
                raw_properties[tag.name] = {"size": tag.size, "offset": value_start}
                archive.seek(archive.tell() + tag.size)

    # 读取 Pins 数组
    pins_offset = node_export.script_serial_offset + node_export.script_serial_size
    archive.seek(node_export.serial_offset + pins_offset)

    # 跳过 end marker
    _end_marker = archive.read_i32()
    pins_count = archive.read_i32()

    if pins_count < 0:
        raise ParseError(f"Invalid pins_count {pins_count} (negative) at node {node_name}")
    if pins_count > MAX_PINS_PER_NODE:
        raise ParseError(f"pins_count {pins_count} exceeds MAX_PINS_PER_NODE {MAX_PINS_PER_NODE} at node {node_name}")

    pins: List[UEdGraphPin] = []
    for _ in range(pins_count):
        # Always read header (24 bytes): b_null + OwningNode_1 + PinGuid_1
        b_null_ptr = archive.read_i32()
        owning_1 = archive.read_i32()
        guid_1 = archive.read_bytes(16)

        if b_null_ptr != 0:
            # NULL pin reference: body still exists, must consume it to advance position
            try:
                read_ue_graph_pin(archive, name_map, summary, export_map, import_map)
            except Exception:
                # If body parsing fails, estimate body size (~180 bytes) and skip
                archive.seek(archive.tell() + 180)
            continue

        try:
            pin = read_ue_graph_pin(archive, name_map, summary, export_map, import_map)
            pins.append(pin)
        except Exception:
            continue

    # UE4 format: read pos/guid/comment after pins if not already from PropertyTags
    if node_guid == "":
        node_pos_x = archive.read_i32()
        node_pos_y = archive.read_i32()
        node_guid = archive.read_bytes(16).hex()
        node_comment = archive.read_fstring()

    class_name = resolve_class_name(node_export.class_index, import_map, export_map) or ""

    base_node = UEdGraphNode(
        node_guid=node_guid,
        node_pos_x=node_pos_x,
        node_pos_y=node_pos_y,
        node_comment=node_comment,
        pins=pins,
        class_name=class_name,
    )

    return create_node_from_archive(
        archive, name_map, summary, export_map, import_map, node_export, base_node,
        raw_properties=raw_properties if raw_properties else None,
    )


# ============================================================================
# UEdGraph 读取
# ============================================================================

def read_ue_graph(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    graph_export: ObjectExport,
    graph_class: str,
    graph_export_idx: int = 0,
) -> UEdGraph:
    """读取 UEdGraph 容器（EdGraph.cpp）。"""
    archive.seek(graph_export.serial_offset)

    # 1. Schema
    schema_index = archive.read_i32()
    schema: Optional[str] = None
    if schema_index != 0:
        schema = resolve_class_name(PackageIndex(schema_index), import_map, export_map)

    # 2. Nodes array
    nodes_count = archive.read_i32()
    if nodes_count < 0:
        raise ParseError(f"Invalid nodes_count {nodes_count} (negative) at graph {graph_export.object_name}")
    if nodes_count > MAX_NODES_PER_GRAPH:
        raise ParseError(f"nodes_count {nodes_count} exceeds MAX_NODES_PER_GRAPH {MAX_NODES_PER_GRAPH} at graph {graph_export.object_name}")

    nodes: List[UEdGraphNode] = []
    failed_nodes: List[str] = []

    for _ in range(nodes_count):
        node_index = archive.read_i32()
        if node_index > 0 and node_index <= len(export_map):
            node_export = export_map[node_index - 1]
            try:
                node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export)
                nodes.append(node)
            except ParseError:
                failed_nodes.append(node_export.object_name)

    # UE 5.x: nodes_count == 0, collect by outer_index
    if nodes_count == 0 and graph_export_idx > 0:
        for node_export in export_map:
            if node_export.outer_index.index == graph_export_idx:
                node_class = get_asset_class(node_export, import_map, export_map)
                if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
                    try:
                        node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export)
                        nodes.append(node)
                    except ParseError:
                        nodes.append(UEdGraphNode(
                            node_guid="",
                            node_pos_x=0,
                            node_pos_y=0,
                            node_comment="",
                            pins=[],
                            class_name=node_class or "",
                            node_data={"_parse_error": True, "node_name": node_export.object_name},
                        ))

    # 3. GraphGuid
    graph_guid_bytes = archive.read_bytes(16)
    graph_guid = graph_guid_bytes.hex()

    # 4. bEditable
    b_editable = archive.read_u8() != 0

    return UEdGraph(
        graph_name=graph_export.object_name,
        graph_class=graph_class,
        schema=schema,
        nodes=nodes,
        graph_guid=graph_guid,
        b_editable=b_editable,
    )
