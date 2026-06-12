"""蓝图图二进制序列化器 — FEdGraphPinType, UEdGraphPin, UEdGraphNode, UEdGraph 读取函数。

等价迁移 uasset_read.py L3191-4679。
Pin 字段级诊断钩子 (trace_mode)。
"""
from __future__ import annotations

import json
import logging
import os
import struct
import threading
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import (
    MAX_PINS_PER_NODE, MAX_NODES_PER_GRAPH, MAX_LINKEDTO_PER_PIN, MAX_FTEXT_CONSUMPTION,
    START_EVENT_TYPES, CONTROL_FLOW_NODES, BRANCH_TYPE_MAP,
    FFRAMEWORK_OBJECT_VERSION_GUID, FUE5_MAINSTREAM_VERSION_GUID, FRELEASE_OBJECT_VERSION_GUID,
    FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE, FFRAMEWORK_VERSION_PINS_STORE_FNAME,
    FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX,
    FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER,
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
    FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION,
    UE5_PROPERTY_TAG_EXTENSION,
)

logger = logging.getLogger(__name__)

_thread_local = threading.local()


def _format_guid_bytes(data: bytes, uppercase: bool = True) -> str:
    """Format 16 raw FGuid bytes as a stable 8-4-4-4-12 string."""
    if len(data) != 16:
        raise ParseError(f"FGuid requires 16 bytes, got {len(data)}")
    text = (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )
    return text.upper() if uppercase else text


def _read_guid(archive: FArchive, uppercase: bool = True) -> str:
    return _format_guid_bytes(archive.read_bytes(16), uppercase=uppercase)


def _get_thread_local():
    """返回当前线程的隔离诊断状态，避免全局可变状态竞态。"""
    if not hasattr(_thread_local, 'linkedto_failure_seen'):
        _thread_local.linkedto_failure_seen: set[tuple[int, str, str]] = set()
        _thread_local.pin_trace_events: List[Dict[str, Any]] = []
        _thread_local.pin_recovery_events: List[Dict[str, Any]] = []
    return _thread_local

from uasset_read.exceptions import ParseError
from uasset_read.serializers.object_resources import (
    resolve_class_name, resolve_class_name_with_linker,
    get_asset_class, get_asset_class_with_linker,
    PackageIndex,
)
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType, FMemberReference
from uasset_read.models.node_types import (
    K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment,
    K2NodeEnhancedInputAction, K2NodeFunctionEntry, K2NodeMessage,
    K2NodeCallDelegate, K2NodeCallArrayFunction, K2NodeCallParentFunction,
    K2NodeFunctionResult, K2NodeCreateWidget, K2NodeAddDelegate, K2NodeMacroInstance,
    K2NodeAssignDelegate, K2NodeGetDataTableRow, K2NodeLoadAsset, K2NodeSpawnActorFromClass,
)


# ---------------------------------------------------------------------------
# 异常 Pin 计数值检测与恢复
# ---------------------------------------------------------------------------


def get_pin_trace_events() -> Dict[str, List[Dict[str, Any]]]:
    """返回 Pin 字段级诊断快照。"""
    _local = _get_thread_local()
    return {
        "pins": [dict(item) for item in _local.pin_trace_events],
        "recoveries": [dict(item) for item in _local.pin_recovery_events],
    }


def _pin_trace_enabled(explicit: bool = False) -> bool:
    return explicit or os.environ.get("UASSET_READ_PIN_TRACE", "").lower() in {
        "1", "true", "yes", "on",
    }


def _record_pin_recovery(event: Dict[str, Any]) -> None:
    _get_thread_local().pin_recovery_events.append(dict(event))


def _rcn(idx, im, em, lk):
    """Resolve class name - linker version if available."""
    return (resolve_class_name_with_linker(idx, lk) if lk else resolve_class_name(idx, im, em))


def _gac(exp, im, em, lk):
    """Get asset class - linker version if available."""
    return (get_asset_class_with_linker(exp, lk) if lk else get_asset_class(exp, im, em))


# ============================================================================
# PropertyTag helper functions
# ============================================================================

def _read_tag_bool(archive: FArchive, tag) -> bool:
    """读取 PropertyTag 中的 bool 值。

    统一处理 inline bool 与 value body 两种形态：
    - tag.size > 0: 从 value body 读取 i32 (UE5 bool serialization)
    - tag.size == 0: 使用 tag.bool_val (inline bool)

    Args:
        archive: FArchive 实例
        tag: PropertyTag 实例

    Returns:
        bool 值
    """
    def _reader() -> bool:
        if tag.size > 0:
            return archive.read_i32() != 0
        return tag.bool_val != 0

    return read_tag_value_bounded(archive, tag, _reader)


def _read_tag_i32(archive: FArchive, tag) -> int:
    """读取 PropertyTag 中的 int32 值并确保 seek 到 value_end_offset。

    标准化 int property 读取流程。

    Args:
        archive: FArchive 实例
        tag: PropertyTag 实例

    Returns:
        int32 值
    """
    return read_tag_value_bounded(archive, tag, archive.read_i32)


def _read_tag_fname(archive: FArchive, tag, name_map: List[str]) -> str:
    """读取 PropertyTag 中的 FName 值并确保 seek 到 value_end_offset。

    标准化 FName property 读取流程。

    Args:
        archive: FArchive 实例
        tag: PropertyTag 实例
        name_map: 名称映射列表

    Returns:
        FName 字符串
    """
    return read_tag_value_bounded(archive, tag, lambda: archive.read_name(name_map))


# ============================================================================
# FEdGraphPinType 读取
# ============================================================================

def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    import_map: Optional[List[ObjectImport]] = None,
    export_map: Optional[List[ObjectExport]] = None,
    linker: Optional["PackageLinker"] = None,
) -> FEdGraphPinType:
    """解析 FEdGraphPinType（UE5.7 专用 — 自定义序列化路径）。"""
    pin_type = FEdGraphPinType()

    release_version = summary.get_custom_version(FRELEASE_OBJECT_VERSION_GUID, 0)

    # PinCategory / PinSubCategory (UE5 始终使用 FName 格式)
    pin_type.pin_category = archive.read_name(name_map)
    pin_type.pin_subcategory = archive.read_name(name_map)

    # PinSubCategoryObject (FPackageIndex)
    pin_type.pin_subcategory_object = archive.read_i32()
    if pin_type.pin_subcategory_object:
        pkg_idx = PackageIndex(pin_type.pin_subcategory_object)
        try:
            if linker is not None:
                pin_type.pin_subcategory_object_ref = linker.resolve_package_index(pkg_idx)
                if pin_type.pin_subcategory_object_ref is not None:
                    pin_type.pin_subcategory_object_name = getattr(
                        pin_type.pin_subcategory_object_ref, "object_name", None
                    )
            elif import_map is not None and export_map is not None:
                pin_type.pin_subcategory_object_name = _rcn(
                    pkg_idx, import_map, export_map, linker
                )
        except Exception:
            pin_type.pin_subcategory_object_ref = None
            pin_type.pin_subcategory_object_name = None

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

    参考 UE C++ FArchive& operator<<(FString&) 实现

    FString 序列化格式 (UE C++ Archive.h L209-230):
    - length == 0: 空字符串（无数据区）
    - length == -1: 空字符串特殊标记（UE 内部优化，无数据区）
    - length > 0: ANSI 字符串，读取 length bytes
    - length < -1: UTF-16 字符串，读取 (-length * 2) bytes

    修复 length == -1 边界条件（SubPin PinToolTip 常见）。
    """
    length = archive.read_i32()
    if length == 0 or length == -1:
        # length=-1 是 UE 空字符串标记，不读取任何数据
        return ""
    if abs(length) > max_length:
        # 长度异常，回退并返回空字符串
        if archive.tell() >= 4:
            archive.seek(archive.tell() - 4)
        return ""
    if length < -1:
        utf16_len = -length * 2
        if utf16_len > max_length * 2:
            if archive.tell() >= 4:
                archive.seek(archive.tell() - 4)
            return ""
        data = archive.read(utf16_len)
        return data.decode('utf-16', errors='replace').rstrip('\x00')
    data = archive.read(length)
    return data.decode('utf-8', errors='replace').rstrip('\x00')


def _read_ftext_fstring(archive: FArchive) -> str:
    """读取 FText 内部 FString。

    与 _read_fstring_safe 不同，此函数在长度异常时直接抛错，由上层决定
    是否整体回退整个 FText。这样可以避免“少读一部分 body 但继续向后走”
    的隐性错位。
    """
    length = archive.read_i32()
    if length == 0 or length == -1:
        return ""
    if abs(length) > 10_000:
        raise ParseError(f"Invalid FText FString length: {length}")
    if length < -1:
        data = archive.read(-length * 2)
        return data.decode('utf-16', errors='replace').rstrip('\x00')
    data = archive.read(length)
    return data.decode('utf-8', errors='replace').rstrip('\x00')


def _read_ftext_value(
    archive: FArchive,
    tolerant: bool = True,
) -> tuple[str, int, int, int]:
    """读取完整 FText，返回 (value, flags, history_type, consumed)。"""
    start_pos = archive.tell()
    flags = archive.read_i32()
    history_type_raw = archive.read_u8()
    history_type = history_type_raw - 256 if history_type_raw >= 128 else history_type_raw
    value, _ = read_ftext_with_history(archive, history_type, tolerant=tolerant)
    return value, flags, history_type, archive.tell() - start_pos


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
    start_pos = archive.tell()
    value = ""

    if history_type not in range(-1, 11):
        raise ParseError(f"Invalid FText history_type={history_type} at pos {start_pos}")

    if history_type in (-1, 255):
        b_has_culture = archive.read_bool()
        if b_has_culture:
            value = _read_ftext_fstring(archive)
    elif history_type == 0:
        _namespace = _read_ftext_fstring(archive)
        _key = _read_ftext_fstring(archive)
        value = _read_ftext_fstring(archive)
    elif history_type == 1:
        format_text, _, _, _ = _read_ftext_value(archive, tolerant=tolerant)
        arg_count = archive.read_i32()
        if arg_count < 0 or arg_count > 100:
            raise ParseError(f"Invalid FText NamedFormat arg_count={arg_count}")
        format_args: Dict[str, str] = {}
        for _ in range(arg_count):
            arg_name = _read_ftext_fstring(archive)
            arg_type = archive.read_u8()
            arg_value = ""
            if arg_type == 0:
                arg_value = str(archive.read_i64())
            elif arg_type == 1:
                arg_value = str(archive.read_u64())
            elif arg_type == 2:
                arg_value = str(archive.read_f32())
            elif arg_type == 3:
                arg_value = str(archive.read_f64())
            elif arg_type == 4:
                arg_value, _, _, _ = _read_ftext_value(archive, tolerant=tolerant)
            elif arg_type == 5:
                arg_value = str(archive.read_u8())
            else:
                raise ParseError(f"Unsupported FFormatArgumentType={arg_type}")
            format_args[arg_name] = arg_value
        value = format_text
        for key, arg in format_args.items():
            if key:
                value = value.replace("{" + key + "}", arg)
    else:
        raise ParseError(f"Unsupported FText history_type={history_type}")

    consumed = archive.tell() - start_pos
    return value, consumed


# ============================================================================
# Pin 引用辅助函数
# ============================================================================

def validate_pin_reference_at(
    archive: FArchive,
    pos: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None,
) -> Optional[Dict[str, Any]]:
    """校验指定位置的 PinReference 结构有效性。

    不移动指针，只检查指定位置是否符合 PinReference 格式：
    - b_null (i32): 0 表示正常引用，非 0 表示空引用（仅 4 字节）
    - owning_node (i32): 在 import/export 范围内（仅当 b_null == 0）
    - pin_guid (16 bytes): 非全零（除非是 ParentPin 空引用）

    支持 4 字节 null PinReference（b_null != 0 时仅需 4 字节）。

    Returns:
        None: 无效结构
        Dict: {
            "b_null": int,
            "owning_node": int,
            "owning_node_valid": bool,
            "guid_nonzero": bool,
            "valid": bool,
            "reason": str,
            "serialized_size": int,  # 4 for null, 24 for non-null
        }
    """
    import struct

    current_pos = archive.tell()

    file_size = getattr(archive, "_file_size", getattr(archive, "file_size", 0))

    # 至少需要 4 字节读取 b_null
    if file_size and pos + 4 > file_size:
        archive.seek(current_pos)
        return None

    fmt = '>' if getattr(archive, '_byte_swapping', False) else '<'

    archive.seek(pos)
    header_bytes = archive.read(4)
    b_null = struct.unpack(f'{fmt}i', header_bytes[0:4])[0]

    if b_null != 0:
        # Null PinReference: 仅消耗 4 字节
        archive.seek(current_pos)
        return {
            "b_null": b_null,
            "owning_node": 0,
            "owning_node_valid": True,
            "guid_nonzero": False,
            "valid": True,
            "reason": "valid null ref (b_null!=0, no actual pin)",
            "serialized_size": 4,
        }

    # b_null == 0: 需要完整 24 字节
    if file_size and pos + 24 > file_size:
        archive.seek(current_pos)
        return None

    archive.seek(pos)
    header_bytes = archive.read(24)
    archive.seek(current_pos)

    owning_node = struct.unpack(f'{fmt}i', header_bytes[4:8])[0]
    guid_bytes = header_bytes[8:24]
    guid_nonzero = any(b != 0 for b in guid_bytes)

    # 校验 owning_node 范围
    owning_node_abs = abs(owning_node)
    export_count = len(export_map)
    import_count = len(import_map) if import_map else 0
    max_valid_index = export_count + import_count + 50  # 允许一定余量

    owning_node_valid = (
        owning_node == 0 or  # 0 表示无引用
        owning_node_abs < max_valid_index
    )

    # 校验 b_null 语义
    if not owning_node_valid:
        valid = False
        reason = f"owning_node {owning_node} exceeds range 0..{max_valid_index}"
    elif not guid_nonzero:
        # b_null == 0 但 GUID 全零：可能是 ParentPin 空引用或未初始化
        valid = True
        reason = "valid ref with zero guid (parent pin empty)"
    else:
        valid = True
        reason = "valid pin reference"

    return {
        "b_null": b_null,
        "owning_node": owning_node,
        "owning_node_valid": owning_node_valid,
        "guid_nonzero": guid_nonzero,
        "valid": valid,
        "reason": reason,
        "serialized_size": 24,
    }


def peek_valid_pin_array_count(
    archive: FArchive,
    export_map: List[ObjectExport],
    max_count: int = 20,
) -> Optional[int]:
    """不移动指针，检查当前位置是否是有效的 LinkedTo 数组。

    只读取 i32 count，验证范围 0..max_count，检查后续数据是否符合 PinReference 结构。
    如果有效返回 count；否则返回 None。

    用途：在 FText 失败后判断当前位置是否已经是 LinkedTo 数组。
    """
    import struct

    current_pos = archive.tell()
    file_size = getattr(archive, "_file_size", getattr(archive, "file_size", 0))

    # 读取 4 字节 count（不移动指针）
    if current_pos + 4 > file_size:
        return None

    archive.seek(current_pos)
    count_bytes = archive.read(4)
    count = struct.unpack('<i', count_bytes)[0]

    # 验证 count 范围
    if count < 0 or count > max_count:
        archive.seek(current_pos)  # 恢复位置
        return None

    # 如果 count == 0，检查后续是否有 SubPins 数组结构
    # (count=0 后面应该是 SubPins count 或其他 Pin 字段)
    # 简化：count=0 总是有效的
    if count == 0:
        archive.seek(current_pos)
        return 0

    # count > 0：检查第一个 PinReference header
    # PinReference header: b_null (i32) + owning_node (i32) + pin_guid (16 bytes)
    if current_pos + 4 + 4 > file_size:
        archive.seek(current_pos)
        return None

    b_null_bytes = archive.read(4)
    b_null = struct.unpack('<i', b_null_bytes)[0]

    archive.seek(current_pos)  # 恢复位置

    # b_null == 0: 正常 PinReference
    # b_null != 0: 空引用（但 count > 0 意味着有内容，所以 b_null 应该是 0）
    if b_null == 0:
        return count
    else:
        return None


def read_pin_reference(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"] = None,
) -> Optional[dict]:
    """读取单个 Pin 引用（FBlueprintEditorUtils::FPinReference）。"""
    b_null_ptr = archive.read_i32()
    if b_null_ptr != 0:
        return None  # null marker consumed 4 bytes only, no more reading

    owning_node_index = archive.read_i32()
    pin_guid_raw = _read_guid(archive)

    # 归一化为 32 字符大写 hex（移除 dash），与 pin_id 格式一致
    pin_guid = pin_guid_raw.replace("-", "").upper()

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

    # pin_guid 已在上方归一化为 32 字符大写 hex（无 dash）
    result = {
        "owning_node": owning_node_name,
        "pin_guid": pin_guid,
    }

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
    recovery_context: str = "linkedto",  # 区分 linkedto vs subpins
) -> List[dict]:
    """读取 Pin 引用数组（SerializePinArray 格式）。

    滑动恢复机制 — count 异常时扫描附近字节寻找合法 i32 count，
    验证候选后恢复解析，避免单个字段错位导致整个 pin 数组丢失。

    恢复上下文标记，区分 LinkedTo 恢复和 SubPins 恢复。
    """
    array_count = archive.read_i32()

    if array_count < 0 or array_count > MAX_LINKEDTO_PER_PIN:
        # 滑动恢复：在当前指针 ±8 字节范围内扫描合法 count
        recovery_pos = archive.tell()
        recovered = _recover_pin_array_count(
            archive, recovery_pos, array_count, export_map, import_map
        )
        if recovered is not None:
            original_bad_count = array_count
            array_count = recovered["count"]
            _record_pin_recovery({
                "kind": "pin_array_count",
                "context": recovery_context,
                "bad_count": original_bad_count,
                "candidate_pos": recovered["candidate_pos"],
                "confidence": recovered["confidence"],
                "reason": recovered["reason"],
            })
            if recovered["confidence"] == "low" and recovery_context == "linkedto":
                # 低置信度恢复不参与 LinkedTo 连接构建，避免污染后续语义
                logger.info(
                    "[P73-RECOVERY] %s low-confidence recovered (count=%d, reason=%s) -> ignored",
                    recovery_context, array_count, recovered["reason"]
                )
                return []
            logger.info(
                "[P73-RECOVERY] %s recovered: count=%d, confidence=%s, reason=%s",
                recovery_context, array_count, recovered["confidence"], recovered["reason"]
            )
        else:
            if array_count < 0:
                raise ParseError(f"Invalid pin array count: {array_count} (negative)")
            raise ParseError(
                f"Pin array count {array_count} exceeds MAX_LINKEDTO_PER_PIN {MAX_LINKEDTO_PER_PIN}"
            )

    pins: List[dict] = []
    for _ in range(array_count):
        ref_pos = archive.tell()
        ref_validation = validate_pin_reference_at(
            archive, ref_pos, export_map, import_map
        )
        if ref_validation is None or not ref_validation["valid"]:
            reason = ref_validation["reason"] if ref_validation else "not enough bytes"
            raise ParseError(
                f"Invalid pin reference at pos {ref_pos} in {recovery_context}: {reason}"
            )
        pin_ref = read_pin_reference(archive, name_map, export_map, import_map, linker)
        if pin_ref is not None:
            pins.append(pin_ref)
    return pins


def _recover_pin_array_count(
    archive: FArchive,
    error_pos: int,
    bad_count: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None,
    scan_window: int = 16,
) -> Optional[Dict[str, Any]]:
    """滑动恢复增强校验（Phase 75: 动态窗口）。

    扫描 error_pos ± scan_window 寻找合法 i32 count (0..20)。

    scan_window 根据 bad_count 大小动态调整：
    - bad_count <= 20: 基础窗口 16 字节
    - bad_count <= 100: 窗口 32 字节
    - bad_count > 100: 窗口 64 字节

    改进：
    - count=0 不能单独作为成功条件，需要验证后续是否有合理结构
    - count>0 必须验证全部或至少前两个 PinReference
    - 恢复成功返回结构化结果：{count, candidate_pos, confidence, reason}

    Returns:
        None: 恢复失败
        Dict: {
            "count": int,
            "candidate_pos": int,
            "confidence": "high"/"medium"/"low",
            "reason": str,
        }
    """
    import struct

    # Phase 75: 动态调整 scan_window
    if bad_count > 100:
        scan_window = max(scan_window, 64)
    elif bad_count > 20:
        scan_window = max(scan_window, 32)

    current_pos = archive.tell()
    search_start = max(0, error_pos - scan_window)
    search_end = min(archive._file_size, error_pos + scan_window)

    archive.seek(search_start)
    window = archive.read(search_end - search_start)

    best_candidate = None
    best_confidence = "low"
    best_reason = ""

    for offset in range(0, len(window) - 4, 1):
        candidate_bytes = window[offset:offset + 4]
        candidate = struct.unpack('<i', candidate_bytes)[0]
        if candidate < 0 or candidate > 20:
            continue  # 不合理范围

        candidate_pos = search_start + offset
        after_count = offset + 4

        # count=0 需要额外验证后续结构
        if candidate == 0:
            # count=0 后面应该是 SubPins 数组或其他合理结构
            # 检查是否有另一个小整数 count (0..20) 紧随其后
            if after_count + 4 <= len(window):
                next_val = struct.unpack('<i', window[after_count:after_count + 4])[0]
                if 0 <= next_val <= 20:
                    # 后面有另一个数组 count，符合 SubPins 结构
                    best_candidate = (candidate_pos, candidate)
                    best_confidence = "medium"
                    best_reason = "count=0 followed by valid SubPins count"
                    # 不 break，继续寻找更高置信度的候选
                    continue
            # count=0 但后续结构不明，置信度低（仅作为最后兜底）
            if best_candidate is None:
                best_candidate = (candidate_pos, candidate)
                best_confidence = "low"
                best_reason = "count=0 without verified subsequent structure"
            continue

        # count > 0: 验证 PinReference 结构
        if after_count + 24 > len(window):
            continue  # 空间不足

        # 验证第一个 PinReference
        pin_ref_1 = validate_pin_reference_at(
            archive, candidate_pos + 4, export_map, import_map
        )
        if pin_ref_1 is None or not pin_ref_1["valid"]:
            continue

        # 验证第二个 PinReference（如果 count >= 2）
        if candidate >= 2 and after_count + 48 <= len(window):
            pin_ref_2 = validate_pin_reference_at(
                archive, candidate_pos + 4 + 24, export_map, import_map
            )
            if pin_ref_2 is None or not pin_ref_2["valid"]:
                # 第二个 ref 无效，置信度中等
                best_candidate = (candidate_pos, candidate)
                best_confidence = "medium"
                best_reason = f"count={candidate}, ref1 valid but ref2 invalid"
                continue

        # 所有验证通过，高置信度
        best_candidate = (candidate_pos, candidate)
        best_confidence = "high"
        best_reason = f"count={candidate}, all refs validated"
        break  # 找到高置信度候选，停止搜索

    if best_candidate is not None:
        candidate_pos, recovered_count = best_candidate
        logger.warning(
            "[P73-RECOVERY] LinkedTo: bad count %d at pos %d, "
            "found count %d at pos %d (confidence=%s, reason=%s)",
            bad_count, error_pos - 4, recovered_count, candidate_pos,
            best_confidence, best_reason,
        )
        # Seek to just after the valid count (start of first pin ref)
        archive.seek(candidate_pos + 4)
        return {
            "count": recovered_count,
            "candidate_pos": candidate_pos,
            "confidence": best_confidence,
            "reason": best_reason,
        }

    # 恢复失败：seek 回原始错误位置
    archive.seek(current_pos)
    return None


def _try_recover_to_subpins(
    archive: FArchive,
    error_pos: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None,
    max_scan: int = 256,
) -> Optional[Dict[str, Any]]:
    """LinkedTo 失败后恢复到 SubPins。

    扫描策略：在 error_pos 到 error_pos + max_scan 范围内寻找合理的小整数
    (0..20)，验证该位置后的数据是否符合 pin reference header 结构。

    改进：
    - 使用 validate_pin_reference_at() 进行结构校验
    - 区分 linkedto_recovered（找到合法 Pin 数组）和 subpins_resync（跳到下一个结构）
    - 返回结构化恢复结果

    Returns:
        None: 恢复失败
        Dict: {
            "recovered_pos": int,
            "count": int,
            "recovery_type": "linkedto_recovered" / "subpins_resync",
            "reason": str,
        }
    """
    import struct

    scan_start = archive.tell()
    scan_end = min(archive._file_size, scan_start + max_scan)
    archive.seek(scan_start)
    window = archive.read(scan_end - scan_start)

    for offset in range(0, len(window) - 4, 1):
        candidate = struct.unpack('<i', window[offset:offset + 4])[0]
        if candidate < 0 or candidate > 20:
            continue

        candidate_pos = scan_start + offset
        after = offset + 4

        # 使用 validate_pin_reference_at 校验
        if candidate > 0 and after + 24 <= len(window):
            pin_ref_result = validate_pin_reference_at(
                archive, candidate_pos + 4, export_map, import_map
            )
            if pin_ref_result is not None and pin_ref_result["valid"]:
                recovered_pos = candidate_pos
                archive.seek(recovered_pos)
                # 收敛：此路径仅用于 SubPins 重同步，不再标记为 linkedto_recovered
                recovery_type = "subpins_resync"
                logger.warning(
                    "[P73-SUBPINS] Recovery at pos %d (count=%d, type=%s, reason=%s)",
                    recovered_pos, candidate, recovery_type, pin_ref_result["reason"],
                )
                _record_pin_recovery({
                    "kind": "subpins_resync",
                    "recovered_pos": recovered_pos,
                    "count": candidate,
                    "recovery_type": recovery_type,
                    "reason": pin_ref_result["reason"],
                })
                return {
                    "recovered_pos": recovered_pos,
                    "count": candidate,
                    "recovery_type": recovery_type,
                    "reason": pin_ref_result["reason"],
                }

        # count=0 或 b_null!=0 情况：检查是否是空数组或 null ref
        if after + 4 <= len(window):
            b_null = struct.unpack('<i', window[after:after + 4])[0]
            if b_null != 0:
                # b_null!=0: 空引用，有效
                recovered_pos = candidate_pos
                archive.seek(recovered_pos)
                logger.warning(
                    "[P73-SUBPINS] Recovery to SubPins at pos %d (count=%d, null ref)",
                    recovered_pos, candidate,
                )
                _record_pin_recovery({
                    "kind": "subpins_resync",
                    "recovered_pos": recovered_pos,
                    "count": candidate,
                    "recovery_type": "subpins_resync",
                    "reason": "b_null!=0 null reference",
                })
                return {
                    "recovered_pos": recovered_pos,
                    "count": candidate,
                    "recovery_type": "subpins_resync",  # 跳到下一个结构
                    "reason": "b_null!=0 null reference",
                }

    # 恢复失败，保持在当前位置
    logger.warning(
        "[P73-SUBPINS] Could not find valid structure within %d bytes from pos %d",
        max_scan, error_pos,
    )
    return None
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
    trace_mode: bool = False,  # 字段级诊断开关
) -> UEdGraphPin:
    """读取 UEdGraphPin 完整序列化格式（UE5.7 专用）。

    D-12: UE5 Pin array uses PinReference format with external header:
      - Header: b_null_ptr + owning_node + pin_guid (read by caller)
      - Body: Complete UEdGraphPin (duplicates owning_node + pin_guid + PinName + ...)

    If header_owning_node and header_pin_id provided, skip internal duplicates and use provided values.

    trace_mode=True 时输出字段级诊断日志 [P73-PINTRACE]。
    """
    trace_mode = _pin_trace_enabled(trace_mode)

    # 诊断记录
    _trace_fields: Dict[str, Any] = {}
    if trace_mode:
        _trace_fields["fields"] = []
        def _trace_field(name: str, start: int, end: int, value_preview: str = "",
                         is_exception: bool = False, is_fallback: bool = False):
            """记录单个字段的追踪信息。"""
            _trace_fields["fields"].append({
                "name": name,
                "start": start,
                "end": end,
                "consumed": end - start,
                "value": value_preview[:50],
                "exception": is_exception,
                "fallback": is_fallback,
            })

    # 1. OwningNode - D-12: If header provided, read and discard internal duplicate to advance position
    _field_start = archive.tell()
    if header_owning_node is not None:
        archive.read_i32()  # Discard internal duplicate
        owning_node_index = header_owning_node
    else:
        owning_node_index = archive.read_i32()
    if trace_mode:
        _trace_field("OwningNode", _field_start, archive.tell(), str(owning_node_index))

    # 2. PinId (FGuid 16 bytes) - D-12: If header provided, read and discard internal duplicate
    _field_start = archive.tell()
    if header_pin_id is not None:
        archive.read_bytes(16)  # Discard internal duplicate
        pin_id = header_pin_id
    else:
        pin_id_bytes = archive.read_bytes(16)
        pin_id = pin_id_bytes.hex().upper()
    if trace_mode:
        _trace_field("PinId", _field_start, archive.tell(), pin_id[:16]+"...")

    # 3. PinName — pin_start_pos corresponds to PinName start (after discarding internal duplicates)
    pin_start_pos = archive.tell()
    if trace_mode:
        _trace_fields["pin_start_pos"] = pin_start_pos

    _field_start = archive.tell()
    pin_name = archive.read_name(name_map)
    if trace_mode:
        _trace_field("PinName", _field_start, archive.tell(), pin_name)

    # 4. PinFriendlyName (FText)
    # FText 安全网：记录解析前位置，限制最大消耗
    ftext_start_pos = archive.tell()
    pin_friendly_name: Optional[str] = None
    try:
        pin_friendly_name, flags, history_type, _ = _read_ftext_value(
            archive, tolerant=True
        )
        # FText 安全网：验证消耗字节数
        ftext_consumed = archive.tell() - ftext_start_pos
        if ftext_consumed > MAX_FTEXT_CONSUMPTION:
            logger.warning(
                "[FTEXT-SAFETY] PinFriendlyName consumed %d bytes (> %d), "
                "possible corruption, seeking back to %d",
                ftext_consumed, MAX_FTEXT_CONSUMPTION, ftext_start_pos + 5
            )
            archive.seek(ftext_start_pos + 5)
            # 标记解析失败，使用默认值
            pin_friendly_name = None
        if trace_mode:
            _trace_field("PinFriendlyName", ftext_start_pos, archive.tell(),
                         f"flags={flags},htype={history_type}")
    except Exception as e:
        pin_friendly_name = None
        archive.seek(ftext_start_pos + 5)
        if trace_mode:
            _trace_field("PinFriendlyName", ftext_start_pos, archive.tell(),
                         "", is_exception=True, is_fallback=True)

    # 5. SourceIndex (UE5 始终存在)
    _field_start = archive.tell()
    source_index = archive.read_i32()
    if trace_mode:
        _trace_field("SourceIndex", _field_start, archive.tell(), str(source_index))

    # 6. PinToolTip — FString (NOT FText!)
    # C++ UEdGraphPin::Serialize L1870: Ar << PinToolTip;
    # EdGraphPin.h L380: FString PinToolTip;
    # FString format: i32 length + data (ANSICHAR or UTF16CHAR)
    _field_start = archive.tell()
    try:
        # PinToolTip 常为短字符串，使用安全读取避免异常长度吞偏游标
        pin_tooltip = _read_fstring_safe(archive, max_length=4096)
        # 额外检查：pin_tooltip 专用二进制数据过滤
        # 注意：archive._contains_binary_data 不存在，需要从 archive 模块导入
        from uasset_read.archive import _contains_binary_data
        if _contains_binary_data(pin_tooltip):
            archive.logger.debug(
                "Binary pinTooltip at pos %d for pin '%s' — returning empty",
                archive.tell() - len(pin_tooltip), pin_name
            )
            if trace_mode:
                _trace_field("PinToolTip", _field_start, archive.tell(), "[BINARY]")
            pin_tooltip = ""
        else:
            if trace_mode:
                _trace_field("PinToolTip", _field_start, archive.tell(),
                             pin_tooltip[:30] if pin_tooltip else "[empty]")
    except Exception as e:
        if trace_mode:
            _trace_field("PinToolTip", _field_start, archive.tell(), "",
                         is_exception=True)
        pin_tooltip = ""

    # 7. Direction — u8 for both UE4 and UE5
    _field_start = archive.tell()
    direction = archive.read_u8()
    if trace_mode:
        _trace_field("Direction", _field_start, archive.tell(), str(direction))

    # 8. PinType
    _field_start = archive.tell()
    pin_type = read_ed_graph_pin_type(
        archive, name_map, summary, import_map, export_map, linker
    )
    if trace_mode:
        _trace_field("PinType", _field_start, archive.tell(), "[PinType struct]")

    # 9-10. DefaultValue strings (容错)
    _field_start = archive.tell()
    try:
        # DefaultValue 常为短字面量，使用安全读取避免大块错误消费
        default_value = _read_fstring_safe(archive, max_length=4096)
        if trace_mode:
            from uasset_read.archive import _contains_binary_data
            if _contains_binary_data(default_value):
                _trace_field("DefaultValue", _field_start, archive.tell(), "[BINARY]")
            else:
                _trace_field("DefaultValue", _field_start, archive.tell(),
                             default_value[:30] if default_value else "[empty]")
    except Exception as e:
        if trace_mode:
            _trace_field("DefaultValue", _field_start, archive.tell(), "",
                         is_exception=True)
        default_value = ""

    _field_start = archive.tell()
    try:
        # AutogeneratedDefaultValue 同上，限制异常长度影响
        autogenerated_default_value = _read_fstring_safe(archive, max_length=4096)
        if trace_mode:
            from uasset_read.archive import _contains_binary_data
            if _contains_binary_data(autogenerated_default_value):
                _trace_field("AutogeneratedDefaultValue", _field_start, archive.tell(), "[BINARY]")
            else:
                _trace_field("AutogeneratedDefaultValue", _field_start, archive.tell(),
                             autogenerated_default_value[:30] if autogenerated_default_value else "[empty]")
    except Exception as e:
        if trace_mode:
            _trace_field("AutogeneratedDefaultValue", _field_start, archive.tell(), "",
                         is_exception=True)
        autogenerated_default_value = ""

    # 11. DefaultObject (FPackageIndex)
    _field_start = archive.tell()
    default_object = archive.read_i32()
    if trace_mode:
        _trace_field("DefaultObject", _field_start, archive.tell(), str(default_object))

    # 12. DefaultTextValue (FText) — NICHT FString!
    # UE5 C++: Ar << DefaultTextValue; (EdGraphPin.cpp L1876)
    # FText Serialisierung: flags(i32,4B) + history_type(u8,1B) + body(variable)
    # Siehe read_ftext_with_history() fuer history_type Verarbeitung
    _dtv_start = archive.tell()
    default_text_value: Optional[str] = None
    try:
        default_text_value, _dtv_flags, _dtv_history, _ = _read_ftext_value(
            archive, tolerant=True
        )
        # DefaultTextValue FText 安全网：验证消耗字节数
        dtv_consumed = archive.tell() - _dtv_start
        if dtv_consumed > MAX_FTEXT_CONSUMPTION:
            logger.warning(
                "[FTEXT-SAFETY] DefaultTextValue consumed %d bytes (> %d), "
                "possible corruption, seeking back to %d",
                dtv_consumed, MAX_FTEXT_CONSUMPTION, _dtv_start + 5
            )
            archive.seek(_dtv_start + 5)
            # 标记解析失败，使用默认值
            default_text_value = None
        if trace_mode:
            _trace_field("DefaultTextValue", _dtv_start, archive.tell(),
                         f"flags={_dtv_flags},htype={_dtv_history}")
    except Exception as e:
        archive.seek(_dtv_start + 5)
        if trace_mode:
            _trace_field("DefaultTextValue", _dtv_start, archive.tell(), "",
                         is_exception=True, is_fallback=True)
        logger.debug("DefaultTextValue read failed at pos %d, skipping header: %s",
                     _dtv_start, e)

    # 13. LinkedTo array — 关键诊断点
    linkedto_start = archive.tell()
    linkedto_raw_count: Optional[int] = None
    try:
        _count_pos = archive.tell()
        linkedto_raw_count = archive.read_i32()
        archive.seek(_count_pos)
    except Exception:
        linkedto_raw_count = None
    try:
        linked_to = read_pin_array(archive, name_map, export_map, import_map, linker)
        logger.debug("LinkedTo: %d refs at pos %d", len(linked_to), linkedto_start)
        if trace_mode:
            refs_preview = [ref.get('owning_node', '?') for ref in linked_to[:2]]
            _trace_field("LinkedTo", linkedto_start, archive.tell(),
                         f"raw_count={linkedto_raw_count},count={len(linked_to)},refs={refs_preview}")
    except Exception as e:
        # Phase 75: 改进日志去重，包含 pin_name
        failure_key = (linkedto_start, type(e).__name__, pin_name)
        tl = _get_thread_local()
        if failure_key not in tl.linkedto_failure_seen:
            tl.linkedto_failure_seen.add(failure_key)
            logger.error("LinkedTo read failed at pos %d (pin=%s): %s",
                         linkedto_start, pin_name, e)
        else:
            logger.debug("LinkedTo read failed (deduped) at pos %d (pin=%s): %s",
                         linkedto_start, pin_name, e)
        if trace_mode:
            _trace_field("LinkedTo", linkedto_start, archive.tell(), "",
                         is_exception=True)
        linked_to = []
        # Phase 75: 使用恢复结果
        recovery_result = _try_recover_to_subpins(archive, linkedto_start, export_map, import_map)
        if recovery_result is not None:
            logger.info(
                "[P73-RECOVERY] SubPins resynced: pos=%d, type=%s",
                recovery_result.get("recovered_pos"),
                recovery_result.get("recovery_type"),
            )

    # 14. SubPins array
    subpins_start = archive.tell()
    subpins_raw_count: Optional[int] = None
    try:
        _count_pos = archive.tell()
        subpins_raw_count = archive.read_i32()
        archive.seek(_count_pos)
    except Exception:
        subpins_raw_count = None
    try:
        sub_pins = read_pin_array(archive, name_map, export_map, import_map, linker)
        if trace_mode:
            _trace_field("SubPins", subpins_start, archive.tell(),
                         f"raw_count={subpins_raw_count},count={len(sub_pins)}")
    except Exception:
        # 同上，不尝试恢复
        sub_pins = []
        if trace_mode:
            _trace_field("SubPins", subpins_start, archive.tell(),
                         f"raw_count={subpins_raw_count}", is_exception=True)

    # 15. ParentPin — reuse read_pin_reference() (UE5: null → 4B, non-null → 24B)
    parent_start = archive.tell()
    _pp_ref = read_pin_reference(archive, name_map, export_map, import_map, linker)
    parent_pin = _pp_ref
    if trace_mode:
        _trace_field("ParentPin", parent_start, archive.tell(),
                     f"null={1 if _pp_ref is None else 0},owning={_pp_ref.get('owning_node') if _pp_ref else 'N/A'}")

    # 16. ReferencePassThroughConnection — reuse read_pin_reference() (same pattern as ParentPin)
    ref_pass_through: Optional[dict] = None
    ref_start = archive.tell()
    _ref_ref = read_pin_reference(archive, name_map, export_map, import_map, linker)
    ref_pass_through = _ref_ref
    if trace_mode:
        _trace_field("ReferencePassThroughConnection", ref_start, archive.tell(),
                     f"null={1 if _ref_ref is None else 0},owning={_ref_ref.get('owning_node') if _ref_ref else 'N/A'}")

    # 17. PersistentGuid (EditorOnly)
    persistent_start = archive.tell()
    try:
        persistent_guid = _read_guid(archive)
    except Exception:
        persistent_guid = None
    if trace_mode:
        _trace_field("PersistentGuid", persistent_start, archive.tell(),
                     persistent_guid or "")

    # 18. BitField (EditorOnly) — uint32 in both UE4 and UE5 (EdGraphPin.cpp L1902)
    hidden = False
    not_connectable = False
    advanced_view = False
    orphaned_pin = False
    try:
        bitfield_start = archive.tell()
        bitfield = archive.read_u32()
        hidden = bool(bitfield & (1 << 0))
        not_connectable = bool(bitfield & (1 << 1))
        advanced_view = bool(bitfield & (1 << 4))
        orphaned_pin = bool(bitfield & (1 << 5))
        if trace_mode:
            _trace_field("BitField", bitfield_start, archive.tell(), str(bitfield))
    except Exception:
        pass

    default_object_ref = None
    if linker is not None and default_object not in (None, 0):
        try:
            default_object_ref = linker.resolve_package_index(PackageIndex(default_object))
        except Exception:
            default_object_ref = None

    # 从 raw dict 中提取对象引用
    linked_to_objects = [pin.get("owning_node_object") for pin in linked_to]
    sub_pins_objects = [pin.get("owning_node_object") for pin in sub_pins]
    parent_pin_object = parent_pin.get("owning_node_object") if parent_pin else None
    ref_pass_through_object = ref_pass_through.get("owning_node_object") if ref_pass_through else None

    # 诊断日志输出
    if trace_mode:
        # 找出第一个可能错位的字段
        first_misaligned = ""
        for f in _trace_fields["fields"]:
            if f.get("exception") and not f.get("fallback"):
                first_misaligned = f["name"]
                break
            # 检查 [BINARY] 标记
            if "[BINARY]" in str(f.get("value", "")):
                first_misaligned = f["name"]
                break

        logger.info(
            "[P73-PINTRACE] Pin '%s' at pos %d: fields=%d, linkedto=%d, first_misaligned='%s'",
            pin_name, pin_start_pos, len(_trace_fields["fields"]),
            len(linked_to), first_misaligned
        )
        _get_thread_local().pin_trace_events.append({
            "pin_name": pin_name,
            "pin_id": pin_id,
            "pin_start_pos": pin_start_pos,
            "linkedto_start": linkedto_start,
            "linkedto_raw_count": linkedto_raw_count,
            "linkedto_count": len(linked_to),
            "subpins_start": subpins_start,
            "subpins_raw_count": subpins_raw_count,
            "subpins_count": len(sub_pins),
            "first_misaligned": first_misaligned,
            "fields": [dict(item) for item in _trace_fields["fields"]],
        })
        # 详细字段日志（可选，调试时启用）
        if first_misaligned:
            logger.debug("[P73-PINTRACE] Fields detail: %s", json.dumps(_trace_fields["fields"]))

    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        pin_friendly_name=pin_friendly_name,
        pin_tooltip=pin_tooltip,
        direction=direction,
        pin_type=pin_type,
        default_value=default_value,
        auto_default_value=autogenerated_default_value,
        default_object=default_object,
        default_object_ref=default_object_ref,
        default_text_value=default_text_value,
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
    """读取 FMemberReference（MemberReference.h L74-95）。"""
    member_parent_index = archive.read_i32()
    member_parent: Optional[str] = None
    if member_parent_index != 0:
        member_parent = _rcn(
            PackageIndex(member_parent_index), import_map, export_map, linker
        )

    member_scope = archive.read_fstring()
    member_name = archive.read_name(name_map)
    member_guid = _read_guid(archive, uppercase=False)
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
                node._export_index = node_index  # tag for dedup
                nodes.append(node)
            except ParseError:
                failed_nodes.append(node_export.object_name)

    # UE 5.x fallback: always scan export_map for nodes whose outer is this graph.
    # Main path nodes_count can be incomplete due to UE5 serialization differences;
    # fallback discovery via outer_index scan catches the rest. Dedup by _export_index.
    if graph_export_idx > 0:
        if len(nodes) > 0:
            logger.debug("Main path collected %d nodes but fallback still triggered — merging with outer_index scan", len(nodes))
        collected_object_names = {n.class_name for n in nodes}  # quick dedup hint
        for node_export in export_map:
            if node_export.outer_index.index == graph_export_idx:
                node_class = _gac(node_export, import_map, export_map, linker)
                if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
                    # Skip if already collected by main path (same export index)
                    node_idx = export_map.index(node_export) + 1
                    already_collected = any(
                        getattr(n, '_export_index', None) == node_idx
                        for n in nodes
                    )
                    if already_collected:
                        continue
                    try:
                        node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export, linker)
                        node._export_index = node_idx  # tag for dedup
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
                        nodes[-1]._export_object_name = node_export.object_name

    # 3. GraphGuid
    graph_guid = _read_guid(archive, uppercase=False)

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
