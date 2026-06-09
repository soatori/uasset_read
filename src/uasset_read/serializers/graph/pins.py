"""UEdGraphPin 序列化器 — Pin 读取函数。"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import (
    MAX_FTEXT_CONSUMPTION, MAX_LINKEDTO_PER_PIN,
)
from uasset_read.exceptions import ParseError
from uasset_read.models.core import UEdGraphPin
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.serializers.graph._common import (
    _read_guid, _get_thread_local, _pin_trace_enabled, _record_pin_recovery,
    _read_fstring_safe, _read_ftext_value,
    validate_pin_reference_at, _recover_pin_array_count, _try_recover_to_subpins,
    peek_valid_pin_array_count,
)
from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type

logger = logging.getLogger(__name__)


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
