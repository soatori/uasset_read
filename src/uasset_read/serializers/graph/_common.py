"""Shared utilities for graph serialization — GUID, FText, thread-local helpers."""
from __future__ import annotations

import logging
import os
import struct
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.exceptions import ParseError
from uasset_read.serializers.property_tags import read_tag_value_bounded

logger = logging.getLogger(__name__)

# Thread-local state for pin tracing
_thread_local = threading.local()


def _get_thread_local():
    """返回当前线程的隔离诊断状态，避免全局可变状态竞态。"""
    if not hasattr(_thread_local, 'linkedto_failure_seen'):
        _thread_local.linkedto_failure_seen: set[tuple[int, str, str]] = set()
        _thread_local.pin_trace_events: List[Dict[str, Any]] = []
        _thread_local.pin_recovery_events: List[Dict[str, Any]] = []
    return _thread_local


def get_pin_trace_events() -> Dict[str, List[Dict[str, Any]]]:
    """返回 Pin 字段级诊断快照。"""
    _local = _get_thread_local()
    return {
        "pins": [dict(item) for item in _local.pin_trace_events],
        "recoveries": [dict(item) for item in _local.pin_recovery_events],
    }


def reset_pin_trace_events() -> None:
    """重置 Pin 追踪事件（用于每次解析前清理）。"""
    _local = _get_thread_local()
    _local.linkedto_failure_seen.clear()
    _local.pin_trace_events.clear()
    _local.pin_recovery_events.clear()


def _record_pin_recovery(event: Dict[str, Any]) -> None:
    _get_thread_local().pin_recovery_events.append(dict(event))


def _pin_trace_enabled(explicit: bool = False) -> bool:
    return explicit or os.environ.get("UASSET_READ_PIN_TRACE", "").lower() in {
        "1", "true", "yes", "on",
    }


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


def _rcn(idx, im, em, lk):
    """Resolve class name - linker version if available."""
    from uasset_read.serializers.object_resources import (
        resolve_class_name, resolve_class_name_with_linker, PackageIndex,
    )
    return (resolve_class_name_with_linker(idx, lk) if lk else resolve_class_name(idx, im, em))


def _gac(exp, im, em, lk):
    """Get asset class - linker version if available."""
    from uasset_read.serializers.object_resources import (
        get_asset_class, get_asset_class_with_linker,
    )
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
# FText / FString reading
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
    是否整体回退整个 FText。这样可以避免"少读一部分 body 但继续向后走"
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
# Pin reference validation helpers
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


def _recover_pin_array_count(
    archive: FArchive,
    error_pos: int,
    bad_count: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None,
    scan_window: int = 16,
) -> Optional[Dict[str, Any]]:
    """滑动恢复增强校验（Phase 75: 动态窗口）。

    扫描 error_pos ± scan_window 寻找合法 i32 count (0..20).

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
