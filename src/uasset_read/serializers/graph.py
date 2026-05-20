"""蓝图图二进制序列化器 — FEdGraphPinType, UEdGraphPin, UEdGraphNode, UEdGraph 读取函数。

等价迁移 uasset_read.py L3191-4679。
Phase 31: 蓝图图解析模块 (per MOD-09)。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

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
from uasset_read.serializers.object_resources import (
    resolve_class_name, resolve_class_name_with_linker,
    get_asset_class, get_asset_class_with_linker,
    PackageIndex,
)
from uasset_read.serializers.property_tags import read_property_tag
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType, FMemberReference
from uasset_read.models.node_types import K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment, K2NodeEnhancedInputAction, K2NodeFunctionEntry


def _rcn(idx, im, em, lk):
    """Resolve class name - linker version if available."""
    return (resolve_class_name_with_linker(idx, lk) if lk else resolve_class_name(idx, im, em))


def _gac(exp, im, em, lk):
    """Get asset class - linker version if available."""
    return (get_asset_class_with_linker(exp, lk) if lk else get_asset_class(exp, im, em))


# ============================================================================
# FEdGraphPinType 读取
# ============================================================================

def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> FEdGraphPinType:
    """解析 FEdGraphPinType（UE5.7 专用 — 自定义序列化路径）。"""
    pin_type = FEdGraphPinType()

    release_version = summary.get_custom_version(FRELEASE_OBJECT_VERSION_GUID, 0)

    # PinCategory / PinSubCategory (UE5 始终使用 FName 格式)
    pin_type.pin_category = archive.read_name(name_map)
    pin_type.pin_subcategory = archive.read_name(name_map)

    # PinSubCategoryObject
    pin_type.pin_subcategory_object = archive.read_i32()

    # ContainerType (UE5 始终使用现代 uint8 格式)
    pin_type.container_type = archive.read_u8()
    if pin_type.container_type == 3:  # Map
        archive.read_name(name_map)  # TerminalCategory
        archive.read_name(name_map)  # TerminalSubCategory
        archive.read_i32()           # TerminalSubCategoryObject

    # bIsReference / bIsWeakPointer (UE5 FArchive bool = uint32, 4B)
    pin_type.is_reference = archive.read_bool()
    pin_type.is_weak_pointer = archive.read_bool()

    # FSimpleMemberReference (UE5 始终存在)
    archive.read_i32()       # MemberParent
    archive.read_name(name_map)  # MemberName
    archive.read_bytes(16)   # MemberGuid

    # bIsConst (UE5 FArchive bool = uint32, 4B)
    pin_type.is_const = archive.read_bool()

    # bIsUObjectWrapper (UE5 FArchive bool = uint32, 4B)
    pin_type.is_uobject_wrapper = archive.read_bool()

    # bSerializeAsSinglePrecisionFloat (UE5 FArchive bool = uint32, 4B)
    pin_type.b_serialize_as_single_precision_float = archive.read_bool()

    return pin_type


# ============================================================================
# FText 读取（UE5 多 history_type 支持）
# ============================================================================

def _read_fstring_safe(archive: FArchive, max_length: int = 10_000) -> str:
    """读取 FString，对异常长度进行容错处理。
    
    TODO: 使用UE编辑器源码的加载方式替换实现代码
    参考 UE C++ FArchive& operator<<(FString&) 实现

    如果长度不合理（超过 max_length），尝试读取为 0 字节空字符串。
    """
    # TODO: 使用UE编辑器源码的加载方式替换实现代码
    length = archive.read_i32()  # TODO: 使用UE编辑器方式读取FString长度
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
        data = archive.read(utf16_len)  # TODO: 使用UE编辑器方式读取UTF-16数据
        return data.decode('utf-16', errors='replace').rstrip('\x00')
    data = archive.read(length)  # TODO: 使用UE编辑器方式读取UTF-8数据
    return data.decode('utf-8', errors='replace').rstrip('\x00')


def _read_ftext_fstring(archive: FArchive) -> str:
    """读取 FText 内部的 FString，对异常长度不回退（已消费 i32 长度字段）。
    
    TODO: 使用UE编辑器源码的加载方式替换实现代码
    参考 UE C++ FArchive& operator<<(FString&) 实现

    与 _read_fstring_safe 的关键区别：长度异常时不回退 seek，
    直接返回空字符串，确保 FText 内部每个 FString 即使长度异常，
    文件位置也不会错位。
    """
    # TODO: 使用UE编辑器源码的加载方式替换实现代码
    length = archive.read_i32()  # TODO: 使用UE编辑器方式读取FString长度
    if length == 0:
        return ""
    if abs(length) > 10_000:
        # 异常长度，不回退（已消费 i32），返回空字符串
        return ""
    if length < 0:
        data = archive.read(-length * 2)  # TODO: 使用UE编辑器方式读取UTF-16数据
        return data.decode('utf-16', errors='replace').rstrip('\x00')
    data = archive.read(length)  # TODO: 使用UE编辑器方式读取UTF-8数据
    return data.decode('utf-8', errors='replace').rstrip('\x00')


def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
) -> tuple[str, int]:
    """读取 FText，返回 (值, 消耗字节数)。

    history_type (ETextHistoryType, signed int8):
    - -1 (0xFF): None（无历史）- bHasCultureInvariantString (bool=4 bytes) + optional FString
    - 0: Base - Namespace (FString) + Key (FString) + SourceString (FString)
    - 1: NamedFormat - FormatText (递归 FText) + Arguments (TArray<FFormatArgumentData>)
    - 2+: 其他生成类型（在 tolerant 模式下不解析）

    参考 UE C++ 源码:
    - Text.cpp L850-1044: FText::SerializeText
    - TextHistory.cpp L792-861: FTextHistory_Base::Serialize
    - TextHistory.cpp L1150-1169: FTextHistory_NamedFormat::Serialize
    - Text.cpp L1680-1761: FFormatArgumentData 序列化
    """
    consumed = 0
    start_pos = archive.tell()
    logger = logging.getLogger(__name__)

    # 新增：验证 history_type 范围
    valid_history_types = list(range(-1, 11))  # -1, 0, 1, ..., 10
    if history_type not in valid_history_types:
        # 无效 history_type：记录 debug 日志并返回空字符串
        logger.debug(
            "Invalid FText history_type %d at pos %d — returning empty",
            history_type, start_pos
        )
        return "", archive.tell() - start_pos
    
    try:
        if history_type == 255 or history_type == -1:  # None (0xFF unsigned or -1 signed)
            # None: flags(4) + htype(1) + bHasCultureInvariantString
            # UE C++ FArchive::operator<<(bool&) 序列化为 uint32 (4 bytes)
            # 参考 Text.cpp L935-944: Ar << bHasCultureInvariantString
            b_has_culture = archive.read_bool()  # 4 bytes (uint32)
            if b_has_culture:
                # CultureInvariantString (FString)
                archive.read_fstring()
        elif history_type == 0:  # Base
            # Base: 3 FStrings (Namespace, Key, SourceString)
            # 参考 TextHistory.cpp L792-861: FTextHistory_Base::Serialize
            # FTextKey 使用 FString 格式，每个 FString = i32 length + data
            archive.read_fstring()  # Namespace
            archive.read_fstring()  # Key
            archive.read_fstring()  # SourceString
        elif history_type == 1:  # NamedFormat
            # TODO: 使用UE编辑器源码的加载方式替换实现代码
            # NamedFormat: FormatText (递归 FText) + Arguments (TArray<FFormatArgumentData>)
            # 参考 TextHistory.cpp L1150-1169
            # FormatText: 递归 FText (完整序列化)
            _ft_flags = archive.read_i32()
            _ft_htype_raw = archive.read_bytes(1)[0]  # TODO: 使用UE编辑器方式读取FText历史类型
            _ft_htype = _ft_htype_raw if _ft_htype_raw < 128 else _ft_htype_raw - 256
            read_ftext_with_history(archive, _ft_htype, tolerant=True)

            # Arguments: TArray<FFormatArgumentData>
            # TODO: 使用UE编辑器源码的加载方式替换实现代码
            # 参考 Text.cpp L1680-1761
            arg_count = archive.read_i32()
            if arg_count > 0 and arg_count < 100:  # 安全限制
                for _ in range(arg_count):
                    # ArgumentName (FString)
                    _aname_len = archive.read_i32()
                    if _aname_len > 0:
                        archive.read(_aname_len)  # TODO: 使用UE编辑器方式读取参数名称
                    elif _aname_len < 0:
                        archive.read(-_aname_len * 2)  # TODO: 使用UE编辑器方式读取UTF-16参数名称

                    # Type (uint8) - EFormatArgumentType
                    _arg_type = archive.read_u8()

                    # Value - 根据 Type 不同
                    # TODO: 使用UE编辑器源码的加载方式替换实现代码
                    # Int(0): int64, Float(1): float, Double(2): double, Text(3): FText, Gender(4): uint8
                    if _arg_type == 0:  # Int
                        archive.read_i64()  # 或 i32 for legacy  # TODO: 使用UE编辑器方式读取Int64
                    elif _arg_type == 1:  # Float
                        archive.read_bytes(4)  # float  # TODO: 使用UE编辑器方式读取Float
                    elif _arg_type == 2:  # Double
                        archive.read_bytes(8)  # double  # TODO: 使用UE编辑器方式读取Double
                    elif _arg_type == 3:  # Text
                        _tv_flags = archive.read_i32()
                        _tv_htype_raw = archive.read_bytes(1)[0]  # TODO: 使用UE编辑器方式读取FText历史类型
                        _tv_htype = _tv_htype_raw if _tv_htype_raw < 128 else _tv_htype_raw - 256
                        read_ftext_with_history(archive, _tv_htype, tolerant=True)
                    elif _arg_type == 4:  # Gender
                        archive.read_u8()
        else:
            # Other types (OrderedFormat=2, ArgumentFormat=3, AsNumber=4, etc.)
            # 这些类型有各自的复杂结构，无法简单跳过
            # 参考 Text.cpp L965-1037 的其他 history types
            # Tolerant mode: 不尝试跳过，直接返回（由调用者处理）
            if not tolerant:
                raise ParseError(f"Unsupported FText history_type={history_type}")
            # tolerant: 不消费字节，返回当前位置
    except Exception as e:
        if tolerant:
            logger.debug("FText tolerant mode: history_type=%s, error=%s", history_type, e)
            # Fallback: 根据类型保守跳过（带边界检查）
            try:
                if history_type == -1:
                    target_pos = start_pos + 9
                elif history_type == 0:
                    target_pos = start_pos + 12  # 3 个最小 FString (len=0, 各 4 bytes)
                elif history_type == 1:
                    target_pos = start_pos + 20  # FormatText(9) + count(4) + 保守
                else:
                    # 不尝试跳过未知类型，保持当前位置
                    target_pos = start_pos
                # 边界检查：确保不超出文件末尾
                if target_pos <= archive.file_size:
                    archive.seek(target_pos)
            except Exception:
                # 如果 seek 也失败，保持在当前位置
                pass
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
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"] = None,
) -> Optional[dict]:
    """读取单个 Pin 引用（SerializePin 格式）。
    
    TODO: 使用UE编辑器源码的加载方式替换实现代码
    参考 UE C++ FArchive& operator<<(FBlueprintEditorUtils::FPinReference&) 实现
    """
    b_null_ptr = archive.read_i32()
    if b_null_ptr != 0:
        return None

    owning_node_index = archive.read_i32()
    pin_guid_bytes = archive.read_bytes(16)  # TODO: 使用UE编辑器方式读取Pin GUID
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

    result = {"owning_node": owning_node_name, "pin_guid": pin_guid}

    # 如果有 linker，解析 owning_node_index 为对象引用
    if linker is not None and owning_node_index != 0:
        pkg_idx = PackageIndex(owning_node_index)
        if not pkg_idx.is_null:
            obj_ref = linker.resolve_package_index(pkg_idx)
            result["owning_node_object"] = obj_ref

    return result


def read_pin_array(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"] = None,
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
        pin_ref = read_pin_reference(archive, name_map, export_map, import_map, linker)
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
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"] = None,
    header_owning_node: Optional[int] = None,
    header_pin_id: Optional[str] = None,
) -> UEdGraphPin:
    """读取 UEdGraphPin 完整序列化格式（UE5.7 专用）。

    D-12: UE5 Pin array uses PinReference format with external header:
      - Header: b_null_ptr + owning_node + pin_guid (read by caller)
      - Body: Complete UEdGraphPin (duplicates owning_node + pin_guid + PinName + ...)

    If header_owning_node and header_pin_id provided, skip internal duplicates and use provided values.
    """
    pin_start_pos = archive.tell()

    # 1. OwningNode - D-12: If header provided, read and discard internal duplicate to advance position
    if header_owning_node is not None:
        archive.read_i32()  # Discard internal duplicate
        owning_node_index = header_owning_node
    else:
        owning_node_index = archive.read_i32()

    # 2. PinId (FGuid 16 bytes) - D-12: If header provided, read and discard internal duplicate
    if header_pin_id is not None:
        archive.read_bytes(16)  # Discard internal duplicate
        pin_id = header_pin_id
    else:
        pin_id_bytes = archive.read_bytes(16)
        pin_id = pin_id_bytes.hex().upper()

    # 3. PinName (UE5 始终使用 FName 格式)
    pin_name = archive.read_name(name_map)

    # 4. PinFriendlyName (FText) — EditorOnly, try/except + seek-back
    ftext_start_pos = archive.tell()
    try:
        flags = archive.read_i32()
        history_type = archive.read_u8()
        read_ftext_with_history(archive, history_type, tolerant=True)
    except Exception:
        archive.seek(ftext_start_pos)

    # 5. SourceIndex (UE5 始终存在)
    source_index = archive.read_i32()

    # 6. PinToolTip — FString (NOT FText!)
    # C++ UEdGraphPin::Serialize L1870: Ar << PinToolTip;
    # EdGraphPin.h L380: FString PinToolTip;
    # FString format: i32 length + data (ANSICHAR or UTF16CHAR)
    try:
        pin_tooltip = archive.read_fstring()
        # 额外检查：pin_tooltip 专用二进制数据过滤
        # 注意：archive._contains_binary_data 不存在，需要从 archive 模块导入
        from uasset_read.archive import _contains_binary_data
        if _contains_binary_data(pin_tooltip):
            archive.logger.debug(
                "Binary pinTooltip at pos %d for pin '%s' — returning empty",
                archive.tell() - len(pin_tooltip), pin_name
            )
            pin_tooltip = ""
    except Exception:
        pin_tooltip = ""

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
        )
    except Exception:
        # Extrem tolerant: Falls FText-Lesen fehlschlaegt, DefaultTextValue ignorieren
        pass

    # 13. LinkedTo array
    linkedto_start = archive.tell()
    try:
        linked_to = read_pin_array(archive, name_map, export_map, import_map, linker)
    except Exception:
        # 不尝试恢复 — 异常可能由数据损坏导致，继续解析可能导致位置不一致
        # 返回空数组，让调用者处理位置不一致问题
        linked_to = []

    # 14. SubPins array
    subpins_start = archive.tell()
    try:
        sub_pins = read_pin_array(archive, name_map, export_map, import_map, linker)
    except Exception:
        # 同上，不尝试恢复
        sub_pins = []

    # 15. ParentPin — UE5: always 24 bytes (b_null + owning + guid)
    _pp_null = archive.read_i32()
    _pp_owning = archive.read_i32()
    _pp_guid_bytes = archive.read_bytes(16)
    _pp_guid = _pp_guid_bytes.hex().upper() if _pp_null == 0 else None
    parent_pin = {"owning_node": None, "pin_guid": _pp_guid} if _pp_null == 0 else None
    if linker is not None and _pp_null == 0 and _pp_owning != 0:
        pkg_idx = PackageIndex(_pp_owning)
        if not pkg_idx.is_null:
            parent_pin["owning_node_object"] = linker.resolve_package_index(pkg_idx)

    # 16. ReferencePassThroughConnection — UE5: always 24 bytes
    ref_pass_through: Optional[dict] = None
    _ref_null = archive.read_i32()
    _ref_owning = archive.read_i32()
    if _ref_null == 0:
        _ref_guid_bytes = archive.read_bytes(16)
        _ref_guid = _ref_guid_bytes.hex().upper()
        ref_pass_through = {"owning_node": None, "pin_guid": _ref_guid}
        if linker is not None and _ref_null == 0 and _ref_owning != 0:
            pkg_idx = PackageIndex(_ref_owning)
            if not pkg_idx.is_null:
                ref_pass_through["owning_node_object"] = linker.resolve_package_index(pkg_idx)

    # 17. PersistentGuid (EditorOnly)
    # TODO: 使用UE编辑器源码的加载方式替换实现代码
    try:
        persistent_guid_bytes = archive.read_bytes(16)  # TODO: 使用UE编辑器方式读取PersistentGuid
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

    # 从 raw dict 中提取对象引用
    linked_to_objects = [pin.get("owning_node_object") for pin in linked_to]
    sub_pins_objects = [pin.get("owning_node_object") for pin in sub_pins]
    parent_pin_object = parent_pin.get("owning_node_object") if parent_pin else None
    ref_pass_through_object = ref_pass_through.get("owning_node_object") if ref_pass_through else None

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
        ref_pass_through=ref_pass_through,
        linked_to_objects=linked_to_objects,
        sub_pins_objects=sub_pins_objects,
        parent_pin_object=parent_pin_object,
        ref_pass_through_object=ref_pass_through_object,
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
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> FMemberReference:
    """读取 FMemberReference（MemberReference.h L74-95）。
    
    TODO: 使用UE编辑器源码的加载方式替换实现代码
    参考 UE C++ FArchive& operator<<(FMemberReference&) 实现
    """
    member_parent_index = archive.read_i32()
    member_parent: Optional[str] = None
    if member_parent_index != 0:
        member_parent = _rcn(
            PackageIndex(member_parent_index), import_map, export_map, linker
        )

    member_scope = archive.read_fstring()
    member_name = archive.read_name(name_map)
    # TODO: 使用UE编辑器源码的加载方式替换实现代码
    member_guid = archive.read_bytes(16).hex()  # TODO: 使用UE编辑器方式读取MemberGuid
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
) -> Dict[str, Any]:
    """读取 K2Node_Event 特有字段，返回字典（作为 node_data）。

    如果 event_reference 已在 PropertyTag 层解析（script_serial），直接使用；
    否则从 archive 当前位置读取 FMemberReference。

    参考 UE C++ FK2Node_Event::Serialize() 实现。
    """
    # D-11: PropertyTag 层已正确解析 EventReference，优先使用
    if event_reference is None:
        event_reference = read_fmember_reference(archive, name_map, import_map, export_map, linker)

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
    r = archive.read_f32()
    g = archive.read_f32()
    b = archive.read_f32()
    a = archive.read_f32()
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
    name_map: List[str]
) -> Dict[str, Any]:
    """读取 K2Node_EnhancedInputAction 特有字段，返回字典（作为 node_data）。"""
    input_action_path = archive.read_fstring()
    return {
        "input_action_path": input_action_path,
    }


def read_k2node_functionentry(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
    function_reference: Optional[FMemberReference] = None,
) -> Dict[str, Any]:
    """读取 K2Node_FunctionEntry 特有字段，返回字典（作为 node_data）。

    FunctionReference 已在 read_ue_graph_node() 中从 PropertyTag 解析。
    """
    return {"function_reference": function_reference}


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
        )
    elif class_name == "K2Node_Knot":
        base_node.node_data = read_k2node_knot(archive)
    elif class_name == "EdGraphNode_Comment":
        base_node.node_data = read_edgraph_node_comment(archive)
    elif class_name == "K2Node_EnhancedInputAction":
        base_node.node_data = read_k2node_enhanced_input(archive, name_map)
        # Populate trigger_events from already-parsed pins
        if isinstance(base_node.node_data, dict):
            base_node.node_data["trigger_events"] = _build_trigger_events_from_pins(base_node.pins)
    elif class_name == "K2Node_FunctionEntry":
        fr = node_refs.get('function_reference') if node_refs else None
        base_node.node_data = read_k2node_functionentry(
            archive, name_map, import_map, export_map, linker,
            function_reference=fr,
        )
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
    linker: Optional["PackageLinker"] = None,
) -> UEdGraphNode:
    """读取 UEdGraphNode 基类字段（含 script_serial PropertyTag 解析）。"""
    archive.seek(node_export.serial_offset)

    node_name = node_export.object_name
    node_class = _gac(node_export, import_map, export_map, linker)

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
            tag = read_property_tag(archive, name_map, tolerant=getattr(archive, '_tolerant', False))
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
                    inner = read_property_tag(archive, name_map)
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
                    member_parent=_rcn(PackageIndex(mp_idx), import_map, export_map, linker) if mp_idx != 0 else None,
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
                    inner = read_property_tag(archive, name_map)
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
                    member_parent=_rcn(PackageIndex(mp_idx), import_map, export_map, linker) if mp_idx != 0 else None,
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
            elif tag.name == "ExtraFlags":
                raw_properties[tag.name] = archive.read_i32()
            elif tag.size > 0:
                # 收集未知 PropertyTag（用于未知节点类型调试和未来扩展）
                value_start = archive.tell()
                raw_properties[tag.name] = {"size": tag.size, "offset": value_start}
                archive.seek(archive.tell() + tag.size)

    # 读取 Pins 数组
    # D-12: UE5 UEdGraphNode Pins format:
    #   - End marker (4 bytes, value=0) after script_serial
    #   - pins_count (i32)
    #   - TArray<UEdGraphPin> elements with header (b_null_ptr + owning_node + pin_guid)
    pins_offset = node_export.script_serial_offset + node_export.script_serial_size + 4  # Skip end marker
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

    node_refs = {
        'function_reference': function_reference,
        'event_reference': event_reference,
    }

    return create_node_from_archive(
        archive, name_map, summary, export_map, import_map, node_export, base_node,
        raw_properties=raw_properties if raw_properties else None,
        linker=linker,
        node_refs=node_refs,
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
    linker: Optional["PackageLinker"] = None,
) -> UEdGraph:
    """读取 UEdGraph 容器（EdGraph.cpp）。
    
    TODO: 使用UE编辑器源码的加载方式替换实现代码
    参考 UE C++ UEdGraph::Serialize() 实现
    """
    archive.seek(graph_export.serial_offset)

    # 1. Schema
    schema_index = archive.read_i32()
    schema: Optional[str] = None
    if schema_index != 0:
        schema = _rcn(PackageIndex(schema_index), import_map, export_map, linker)

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
                node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export, linker)
                nodes.append(node)
            except ParseError:
                failed_nodes.append(node_export.object_name)

    # UE 5.x: nodes_count == 0, collect by outer_index
    if nodes_count == 0 and graph_export_idx > 0:
        for node_export in export_map:
            if node_export.outer_index.index == graph_export_idx:
                node_class = _gac(node_export, import_map, export_map, linker)
                if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
                    try:
                        node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export, linker)
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
    # TODO: 使用UE编辑器源码的加载方式替换实现代码
    graph_guid_bytes = archive.read_bytes(16)  # TODO: 使用UE编辑器方式读取GraphGuid
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
