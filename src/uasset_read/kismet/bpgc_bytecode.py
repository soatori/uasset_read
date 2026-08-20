from __future__ import annotations

"""
BPGC Bytecode Extraction — BlueprintGeneratedClass cooked bytecode parsing.

Extract bytecode from BPGC script_serial_region (fallback
for UE5 cooked Blueprints where Function exports contain no bytecode).

Provides:
- extract_bpgc_bytecode: Read BPGC script region, parse cooked format into per-function buffers
- map_bytecode_to_functions: Map bytecode buffers to Function exports by ordinal position
- _parse_cooked_bytecode_buffer: Pure logic function for buffer splitting
"""

import logging
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from uasset_read.exceptions import ParseError
from uasset_read.constants import UE_NONE_SENTINEL

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary


logger = logging.getLogger(__name__)

# Cooked bytecode end-of-function sentinel variants
_END_OF_SCRIPT = 0x53  # EX_EndOfScript — standard
_COOKED_END_SENTINEL = 0xDD  # Cooked format variant seen in some UE5 assets


# ===========================================================================
# BPGC 提取诊断指标 (#426)
# ===========================================================================


class BytecodeConfidenceLevel(Enum):
    """字节码恢复置信度级别。"""

    HIGH = "high"  # 所有缓冲区数量匹配、哨兵正确、无截断
    MEDIUM = "medium"  # 存在哨兵不匹配或数量不一致，但大部分数据可用
    LOW = "low"  # 存在截断或大量空缓冲区
    UNRECOVERABLE = "unrecoverable"  # 无可用数据


def _find_next_sentinel(data: bytes, start: int) -> int:
    """Scan forward through data to find the next sentinel byte.

    Searches for EX_EndOfScript (0x53) or Cooked end sentinel (0xDD)
    starting from the given offset.

    Args:
        data: Raw bytecode data
        start: Starting offset for the search

    Returns:
        Offset of the next sentinel byte, or -1 if not found.
    """
    for i in range(start, len(data)):
        if data[i] in (_END_OF_SCRIPT, _COOKED_END_SENTINEL):
            return i
    return -1


@dataclass
class BPGCExtractionMetrics:
    """BPGC 字节码提取诊断指标 — 记录提取过程的质量信息。

    用于评估提取结果的可信度，辅助调试和诊断。
    由 _parse_cooked_bytecode_buffer 生成，由 extract_bpgc_bytecode 透传。
    """

    # 原始数据信息
    total_raw_bytes: int = 0  # 脚本区域可用字节总数
    class_script_skipped: bool = False  # 是否跳过了 BPGC class 自身脚本
    class_script_size: int = 0  # 跳过的 class 脚本大小

    # 函数声明与提取
    declared_function_count: int = 0  # header 中声明的函数数量
    extracted_buffer_count: int = 0  # 实际提取的缓冲区数量

    # 缓冲区质量
    empty_buffer_count: int = 0  # 空缓冲区数量 (sz <= 0)
    sentinel_mismatch_count: int = 0  # 未以预期哨兵结束的缓冲区数量
    truncated_buffer_count: int = 0  # 因数据不足而被截断的缓冲区数量

    # 映射质量 (由 map_bytecode_to_functions 填充)
    mapped_function_count: int = 0  # 成功映射到函数的缓冲区数量
    mapping_mismatch: bool = False  # 缓冲区数量与函数导出数量是否不匹配

    # 提取阶段错误
    early_exit: bool = False  # 是否因数据异常提前退出
    exit_reason: str = ""  # 提前退出的原因
    used_sentinel_fallback: bool = False  # 是否使用了哨兵回退解析

    def to_dict(self) -> dict:
        """转为 JSON 兼容字典。零值字段省略以减少输出噪音。"""
        d: dict = {}
        if self.total_raw_bytes:
            d["total_raw_bytes"] = self.total_raw_bytes
        if self.class_script_skipped:
            d["class_script_skipped"] = True
            d["class_script_size"] = self.class_script_size
        if self.declared_function_count:
            d["declared_function_count"] = self.declared_function_count
        if self.extracted_buffer_count:
            d["extracted_buffer_count"] = self.extracted_buffer_count
        if self.empty_buffer_count:
            d["empty_buffer_count"] = self.empty_buffer_count
        if self.sentinel_mismatch_count:
            d["sentinel_mismatch_count"] = self.sentinel_mismatch_count
        if self.truncated_buffer_count:
            d["truncated_buffer_count"] = self.truncated_buffer_count
        if self.mapped_function_count:
            d["mapped_function_count"] = self.mapped_function_count
        if self.mapping_mismatch:
            d["mapping_mismatch"] = True
        if self.early_exit:
            d["early_exit"] = True
            d["exit_reason"] = self.exit_reason
        if self.used_sentinel_fallback:
            d["used_sentinel_fallback"] = True
        return d

    @property
    def confidence(self) -> BytecodeConfidenceLevel:
        """根据指标数据计算置信度级别。"""
        # 无可提取数据
        if self.extracted_buffer_count == 0:
            return BytecodeConfidenceLevel.UNRECOVERABLE

        # 存在截断 → 低置信度
        if self.truncated_buffer_count > 0:
            return BytecodeConfidenceLevel.LOW

        # 大量空缓冲区 (>50%) → 低置信度
        if (
            self.empty_buffer_count > 0
            and self.empty_buffer_count > self.extracted_buffer_count // 2
        ):
            return BytecodeConfidenceLevel.LOW

        # 提前退出 → 低置信度
        if self.early_exit:
            return BytecodeConfidenceLevel.LOW

        # 使用了哨兵回退 → 中等置信度
        if self.used_sentinel_fallback:
            return BytecodeConfidenceLevel.MEDIUM

        # 哨兵不匹配或数量不一致 → 中等置信度
        if self.sentinel_mismatch_count > 0 or self.mapping_mismatch:
            return BytecodeConfidenceLevel.MEDIUM

        # 全部正常 → 高置信度
        return BytecodeConfidenceLevel.HIGH


def _parse_cooked_bytecode_buffer(
    data: bytes,
) -> tuple[list[bytes], BPGCExtractionMetrics]:
    """Parse BPGC script region bytes into per-function bytecode buffers.

    BPGC cooked 格式 (per UStruct/FStructScriptLoader + 实测验证):
    1. [i32 BytecodeBufferSize] — BPGC class 自身脚本大小
    2. [i32 SerializedScriptSize] — BPGC class 脚本序列化大小
    3. [i32 num_functions] — 函数字节码条目数
    4. [num_functions × i32 bytecode_size] — 各函数字节码大小
    5. [concatenated bytecode data] — 拼接的字节码

    当 SerializedScriptSize > 0 时，跳过对应字节的 class 脚本数据。

    Pure logic function — no archive or I/O dependency.

    Args:
        data: Raw script_serial_region content (after PropertyTags + optional headers)

    Returns:
        Tuple of (buffers, metrics):
        - buffers: List of bytecode buffers, one per function
        - metrics: BPGCExtractionMetrics diagnostic data

    Stops on:
        - data too short for header
        - num_functions > 10000 (unreasonable)
        - size exceeding remaining bytes
    """
    buffers: list[bytes] = []
    metrics = BPGCExtractionMetrics(total_raw_bytes=len(data))
    data_len = len(data)
    offset = 0

    # Step 1: Read BPGC class's own script header (BytecodeBufferSize + SerializedScriptSize)
    if data_len < 8:
        logger.debug("BPGC bytecode: data too short for header (%d bytes)", data_len)
        metrics.early_exit = True
        metrics.exit_reason = "data_too_short_for_header"
        return buffers, metrics

    _bb_size = struct.unpack_from("<i", data, offset)[0]
    ss_size = struct.unpack_from("<i", data, offset + 4)[0]
    offset += 8

    # Skip class script data if present (SerializedScriptSize > 0)
    if ss_size > 0:
        if offset + ss_size > data_len:
            logger.debug(
                "BPGC bytecode: class script SerializedScriptSize=%d exceeds data (%d bytes)",
                ss_size,
                data_len - offset,
            )
            metrics.early_exit = True
            metrics.exit_reason = "class_script_exceeds_data"
            return buffers, metrics
        metrics.class_script_skipped = True
        metrics.class_script_size = ss_size
        offset += ss_size

    # Step 2: Read function count
    if offset + 4 > data_len:
        logger.debug("BPGC bytecode: no room for function count at offset %d", offset)
        metrics.early_exit = True
        metrics.exit_reason = "no_room_for_function_count"
        return buffers, metrics

    num_functions = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    metrics.declared_function_count = num_functions

    if num_functions == 0:
        logger.debug("BPGC bytecode: 0 functions declared")
        metrics.early_exit = True
        metrics.exit_reason = "zero_functions_declared"
        return buffers, metrics

    if num_functions > 10000:
        logger.debug(
            "BPGC bytecode: unreasonable function count %d at offset %d",
            num_functions,
            offset - 4,
        )
        metrics.early_exit = True
        metrics.exit_reason = f"unreasonable_function_count_{num_functions}"
        return buffers, metrics

    # Step 3: Read function bytecode sizes
    sizes_end = offset + num_functions * 4
    if sizes_end > data_len:
        logger.debug(
            "BPGC bytecode: not enough data for %d function sizes (need %d, have %d)",
            num_functions,
            sizes_end - offset,
            data_len - offset,
        )
        metrics.early_exit = True
        metrics.exit_reason = "not_enough_data_for_sizes"
        return buffers, metrics

    sizes: list[int] = []
    for i in range(num_functions):
        sz = struct.unpack_from("<i", data, offset)[0]
        sizes.append(sz)
        offset += 4

    # Step 4: Extract function bytecodes from concatenated data
    for i, sz in enumerate(sizes):
        if sz <= 0:
            buffers.append(b"")
            metrics.empty_buffer_count += 1
            continue

        if offset + sz > data_len:
            logger.debug(
                "BPGC bytecode buffer #%d: size=%d exceeds remaining %d bytes",
                i,
                sz,
                data_len - offset,
            )
            # 尝试读取剩余数据
            sz = data_len - offset
            if sz <= 0:
                metrics.truncated_buffer_count += 1
                break
            metrics.truncated_buffer_count += 1

        buf = data[offset : offset + sz]
        offset += sz

        # Validate buffer ends with expected sentinel (tolerant)
        if buf and buf[-1] not in (_END_OF_SCRIPT, _COOKED_END_SENTINEL):
            logger.debug(
                "Bytecode buffer #%d ends with 0x%02X, accepting in tolerant mode",
                i,
                buf[-1],
            )
            metrics.sentinel_mismatch_count += 1

        buffers.append(buf)

    metrics.extracted_buffer_count = len(buffers)
    return buffers, metrics


def _parse_cooked_bytecode_buffer_sentinel_fallback(
    data: bytes,
) -> tuple[list[bytes], BPGCExtractionMetrics]:
    """Parse BPGC script region using sentinel-based recovery.

    This is a fallback strategy activated only when the primary size-based
    parsing returns empty results (e.g., malformed headers, variant formats).
    Scans forward through the byte stream for sentinel bytes (0x53, 0xDD)
    to find function buffer boundaries.

    Args:
        data: Raw script_serial_region content

    Returns:
        Tuple of (buffers, metrics) with used_sentinel_fallback=True
    """
    buffers: list[bytes] = []
    metrics = BPGCExtractionMetrics(total_raw_bytes=len(data))
    metrics.used_sentinel_fallback = True
    data_len = len(data)

    if data_len < 8:
        metrics.early_exit = True
        metrics.exit_reason = "data_too_short_for_sentinel_scan"
        return buffers, metrics

    # Skip the 8-byte header (BytecodeBufferSize + SerializedScriptSize)
    offset = 8

    # Try to read function count, but be lenient
    if offset + 4 <= data_len:
        num_functions = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        metrics.declared_function_count = num_functions

        # If function count looks reasonable, try to read size array
        if 0 < num_functions <= 10000:
            sizes_end = offset + num_functions * 4
            if sizes_end <= data_len:
                # Read sizes and extract buffers using size-based approach
                sizes: list[int] = []
                for _ in range(num_functions):
                    sz = struct.unpack_from("<i", data, offset)[0]
                    sizes.append(sz)
                    offset += 4

                # Extract buffers using declared sizes
                for i, sz in enumerate(sizes):
                    if sz <= 0:
                        buffers.append(b"")
                        metrics.empty_buffer_count += 1
                        continue

                    if offset + sz > data_len:
                        # Size exceeds data, fall through to sentinel scan
                        break

                    buf = data[offset : offset + sz]
                    offset += sz

                    # Validate sentinel (tolerant)
                    if buf and buf[-1] not in (_END_OF_SCRIPT, _COOKED_END_SENTINEL):
                        metrics.sentinel_mismatch_count += 1

                    buffers.append(buf)

                # If we extracted some buffers, return them
                if buffers:
                    metrics.extracted_buffer_count = len(buffers)
                    return buffers, metrics

    # Sentinel-based recovery: scan for sentinel bytes
    logger.debug("BPGC bytecode: falling back to sentinel scan")
    buffers = []
    offset = 8  # Skip header again

    while offset < data_len:
        sentinel_pos = _find_next_sentinel(data, offset)
        if sentinel_pos == -1:
            # No more sentinels, take remaining data as last buffer
            remaining = data[offset:]
            if remaining:
                buffers.append(remaining)
            break

        # Extract buffer up to and including the sentinel
        buf = data[offset : sentinel_pos + 1]
        if buf:
            buffers.append(buf)

        offset = sentinel_pos + 1

    metrics.extracted_buffer_count = len(buffers)
    return buffers, metrics


def extract_bpgc_bytecode(
    archive: FArchive,
    bpgc_export: ObjectExport,
    summary: PackageFileSummary,
    asset_name: str,
    name_map: list[str],
    import_map: list,
    export_map: list,
) -> tuple[dict[str, bytes], BPGCExtractionMetrics]:
    """
    Extract cooked bytecode buffers from a BlueprintGeneratedClass export.

    Reads the BPGC's script_serial_region, skips PropertyTags until "None",
    then parses the cooked bytecode format (u32 size prefix per function buffer)
    into individual bytecode buffers.

    Args:
        archive: FArchive instance (file-level archive)
        bpgc_export: ObjectExport for the BlueprintGeneratedClass
        summary: PackageFileSummary for version flags
        asset_name: Asset name for logging/context
        name_map: Name table for PropertyTag parsing
        import_map: Import table for class resolution
        export_map: Export table for class resolution

    Returns:
        Tuple of (buffers_dict, metrics):
        - buffers_dict: Dict mapping function index (as string "0", "1", ...) to bytecode bytes.
          Empty dict if not a BPGC or no bytecode data.
        - metrics: BPGCExtractionMetrics diagnostic data

    Raises:
        ParseError: If script region structure is invalid
    """
    from uasset_read.serializers.object_resources import (
        detect_blueprint_generated_class,
    )
    from uasset_read.serializers.property_tags import read_property_tag
    from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION

    empty_metrics = BPGCExtractionMetrics()

    # Step 1: Validate BPGC export
    if not detect_blueprint_generated_class(bpgc_export, import_map, export_map):
        logger.debug(
            "Export '%s' is not a BlueprintGeneratedClass, skipping",
            bpgc_export.object_name,
        )
        return {}, empty_metrics

    # Step 2: Check script_serialization
    if not bpgc_export.has_script_serialization:
        logger.debug(
            "BPGC '%s' has no script_serial_region data", bpgc_export.object_name
        )
        return {}, empty_metrics

    # Step 3: Calculate script start position
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        script_start = (
            bpgc_export.serial_offset + bpgc_export.script_serialization_start_offset
        )
    else:
        script_start = bpgc_export.serial_offset

    archive.seek(script_start)

    # Step 3b: SerializationControlExtensions header (same as extract_bytecode_bytes)
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        ctrl = archive.read_u8()
        if ctrl & 0x02:
            archive.read_u8()  # skip overridden operation

    # Step 5: Skip PropertyTags until "None" terminator
    tag_count = 0
    while True:
        tag = read_property_tag(archive, name_map)
        if tag.name == UE_NONE_SENTINEL:
            break
        # Skip property value data using FArchive read_bytes
        archive.read_bytes(tag.size)
        tag_count += 1
        if tag_count > 10000:
            raise ParseError(
                f"Too many PropertyTags (>10000) in BPGC '{bpgc_export.object_name}' script region"
            )

    # Step 6: Read remaining script region bytes and parse cooked format
    region_end = bpgc_export.serial_offset + bpgc_export.serial_size
    current_pos = archive.tell()
    remaining_bytes = region_end - current_pos

    if remaining_bytes <= 0:
        logger.debug(
            "BPGC '%s': no bytecode data after PropertyTags", bpgc_export.object_name
        )
        return {}, empty_metrics

    # 注意: script_serialization_size 仅覆盖 PropertyTags 区域，不包含字节码数据。
    # 字节码数据位于 serial region 的剩余部分（PropertyTags 之后）。

    raw_bytecode = archive.read_bytes(remaining_bytes)

    # Step 7: Parse cooked bytecode buffers
    buffers, metrics = _parse_cooked_bytecode_buffer(raw_bytecode)

    # Step 8: Try sentinel fallback if primary parsing failed
    if not buffers and metrics.early_exit:
        logger.debug(
            "BPGC '%s': primary parsing failed (%s), trying sentinel fallback",
            asset_name,
            metrics.exit_reason,
        )
        buffers, metrics = _parse_cooked_bytecode_buffer_sentinel_fallback(raw_bytecode)

    if not buffers:
        # #343: 区分"无字节码"和"解析失败"
        # 注意：remaining_bytes <= 0 的情况已在上方处理
        logger.debug(
            "BPGC '%s': no bytecode buffers extracted (%d bytes available),"
            " possibly format variant or data corruption",
            asset_name,
            remaining_bytes,
        )
        return {}, metrics

    logger.info(
        "BPGC '%s': extracted %d bytecode buffers from script_serial_region (confidence=%s)",
        bpgc_export.object_name,
        len(buffers),
        metrics.confidence.value,
    )

    # Return dict mapping index string to bytecode bytes
    return {str(i): buf for i, buf in enumerate(buffers)}, metrics


def map_bytecode_to_functions(
    bytecode_buffers: dict[str, bytes],
    function_exports: list[ObjectExport],
    name_map: list[str],
    import_map: list,
    export_map: list,
    metrics: BPGCExtractionMetrics | None = None,
) -> dict[str, bytes]:
    """
    Map bytecode buffers to Function exports by ordinal position.

    UE cooked format convention: bytecode buffers in the BPGC script_serial_region
    are in the same order as Function exports in the export table.

    Args:
        bytecode_buffers: Dict of {index_str: bytecode_bytes} from extract_bpgc_bytecode
        function_exports: List of all ObjectExport entries from the package
        name_map: Name table (unused for ordinal mapping, kept for API consistency)
        import_map: Import table for class resolution
        export_map: Export table for class resolution
        metrics: Optional BPGCExtractionMetrics to update with mapping results

    Returns:
        Dict mapping function_name to bytecode_bytes.
        Empty dict if no matching functions/buffers.
    """
    from uasset_read.serializers.object_resources import resolve_class_name

    # Step 2: Filter to Function-type exports only
    function_type_exports = [
        exp
        for exp in function_exports
        if resolve_class_name(exp.class_index, import_map, export_map)
        in ("Function", "UFunction")
    ]

    if not function_type_exports:
        logger.debug("No Function exports found in export table")
        if metrics is not None:
            metrics.mapping_mismatch = True
        return {}

    # Sort buffers by index key for deterministic ordinal pairing
    # Filter to valid integer keys only (skip any malformed keys)
    def _safe_int(s: str) -> int:
        try:
            return int(s)
        except ValueError:
            return -1

    sorted_indices = sorted(bytecode_buffers.keys(), key=_safe_int)
    # Exclude any keys that couldn't be parsed as int
    sorted_indices = [k for k in sorted_indices if k.isdigit()]
    buffer_list = [bytecode_buffers[i] for i in sorted_indices]

    buf_count = len(buffer_list)
    func_count = len(function_type_exports)

    # Step 5: Log warning on count mismatch
    if buf_count != func_count:
        logger.debug(
            "Bytecode/function count mismatch: %d buffers vs %d Function exports — "
            "mapping by min count",
            buf_count,
            func_count,
        )
        if metrics is not None:
            metrics.mapping_mismatch = True

    # Step 3: Pair by ordinal position
    pair_count = min(buf_count, func_count)
    result = {}
    for i in range(pair_count):
        func_export = function_type_exports[i]
        func_name = func_export.object_name
        result[func_name] = buffer_list[i]

    if metrics is not None:
        metrics.mapped_function_count = len(result)

    logger.info("Mapped %d bytecode buffers to Function exports", len(result))
    return result


# ===========================================================================
# 置信度验证 (#426)
# ===========================================================================


def validate_recovered_bytecode(
    bytecode_bytes: bytes,
    metrics: BPGCExtractionMetrics | None = None,
    function_name: str = "",
) -> tuple[BytecodeConfidenceLevel, list[str]]:
    """验证恢复的字节码可信度。

    对提取到的字节码进行多项启发式检查，返回置信度级别和警告列表。

    检查项:
    - 非空检查
    - 最小长度合理性（至少包含 EX_EndOfScript 哨兵）
    - 起始 token 合法性
    - 尾部哨兵检查
    - 结合 BPGCExtractionMetrics 的提取质量评估

    Args:
        bytecode_bytes: 待验证的字节码原始字节
        metrics: 可选的 BPGCExtractionMetrics，来自提取阶段
        function_name: 函数名（仅用于日志上下文）

    Returns:
        Tuple of (confidence_level, warnings):
        - confidence_level: BytecodeConfidenceLevel 枚举值
        - warnings: 中文警告消息列表
    """
    warnings: list[str] = []

    # 空字节码
    if not bytecode_bytes:
        return BytecodeConfidenceLevel.UNRECOVERABLE, ["字节码为空"]

    data_len = len(bytecode_bytes)

    # 最小长度检查：至少 2 字节（一个 token + EX_EndOfScript）
    if data_len < 2:
        warnings.append(f"字节码过短（{data_len} 字节），无法包含有效表达式")
        return BytecodeConfidenceLevel.UNRECOVERABLE, warnings

    # 起始 token 检查
    first_byte = bytecode_bytes[0]
    if first_byte in (0x00, 0xFF):
        warnings.append(f"起始 token 0x{first_byte:02X} 为填充值，字节码可能损坏")

    # 尾部哨兵检查
    last_byte = bytecode_bytes[-1]
    has_valid_sentinel = last_byte in (_END_OF_SCRIPT, _COOKED_END_SENTINEL)
    if not has_valid_sentinel:
        warnings.append(
            f"尾部字节 0x{last_byte:02X} 不是预期的 EX_EndOfScript(0x53) "
            f"或 Cooked 哨兵(0xDD)"
        )

    # 大小合理性检查：单个函数字节码不应超过 64KB（常见蓝图函数上限）
    if data_len > 65536:
        warnings.append(f"字节码大小 {data_len} 字节异常偏大，可能包含非代码数据")

    # 结合 metrics 进行综合评估
    if metrics is not None:
        if metrics.truncated_buffer_count > 0:
            warnings.append(
                f"提取过程中有 {metrics.truncated_buffer_count} 个缓冲区被截断"
            )
        if metrics.sentinel_mismatch_count > 0:
            warnings.append(
                f"提取过程中有 {metrics.sentinel_mismatch_count} 个缓冲区哨兵不匹配"
            )
        if metrics.mapping_mismatch:
            warnings.append("缓冲区数量与函数导出数量不一致")

    # 综合评估置信度
    if not has_valid_sentinel and any("截断" in w for w in warnings):
        confidence = BytecodeConfidenceLevel.LOW
    elif not has_valid_sentinel or any("截断" in w for w in warnings):
        confidence = BytecodeConfidenceLevel.MEDIUM
    elif warnings:
        confidence = BytecodeConfidenceLevel.MEDIUM
    else:
        confidence = BytecodeConfidenceLevel.HIGH

    if function_name and warnings:
        logger.debug(
            "validate_recovered_bytecode('%s'): confidence=%s, %d warnings",
            function_name,
            confidence.value,
            len(warnings),
        )

    return confidence, warnings
