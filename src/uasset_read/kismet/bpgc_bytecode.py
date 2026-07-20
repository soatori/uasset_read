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
from typing import TYPE_CHECKING

from uasset_read.exceptions import ParseError
from uasset_read.constants import UE_NONE_SENTINEL

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary


logger = logging.getLogger(__name__)

# Cooked bytecode end-of-function sentinel variants
_END_OF_SCRIPT = 0x53        # EX_EndOfScript — standard
_COOKED_END_SENTINEL = 0xDD  # Cooked format variant seen in some UE5 assets


def _parse_cooked_bytecode_buffer(data: bytes) -> list[bytes]:
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
        List of bytecode buffers, one per function

    Stops on:
        - data too short for header
        - num_functions > 10000 (unreasonable)
        - size exceeding remaining bytes
    """
    buffers: list[bytes] = []
    data_len = len(data)
    offset = 0

    # Step 1: Read BPGC class's own script header (BytecodeBufferSize + SerializedScriptSize)
    if data_len < 8:
        logger.debug("BPGC bytecode: data too short for header (%d bytes)", data_len)
        return buffers

    _bb_size = struct.unpack_from('<i', data, offset)[0]
    ss_size = struct.unpack_from('<i', data, offset + 4)[0]
    offset += 8

    # Skip class script data if present (SerializedScriptSize > 0)
    if ss_size > 0:
        if offset + ss_size > data_len:
            logger.debug(
                "BPGC bytecode: class script SerializedScriptSize=%d exceeds data (%d bytes)",
                ss_size, data_len - offset,
            )
            return buffers
        offset += ss_size

    # Step 2: Read function count
    if offset + 4 > data_len:
        logger.debug("BPGC bytecode: no room for function count at offset %d", offset)
        return buffers

    num_functions = struct.unpack_from('<I', data, offset)[0]
    offset += 4

    if num_functions == 0:
        logger.debug("BPGC bytecode: 0 functions declared")
        return buffers

    if num_functions > 10000:
        logger.debug(
            "BPGC bytecode: unreasonable function count %d at offset %d",
            num_functions, offset - 4,
        )
        return buffers

    # Step 3: Read function bytecode sizes
    sizes_end = offset + num_functions * 4
    if sizes_end > data_len:
        logger.debug(
            "BPGC bytecode: not enough data for %d function sizes (need %d, have %d)",
            num_functions, sizes_end - offset, data_len - offset,
        )
        return buffers

    sizes: list[int] = []
    for i in range(num_functions):
        sz = struct.unpack_from('<i', data, offset)[0]
        sizes.append(sz)
        offset += 4

    # Step 4: Extract function bytecodes from concatenated data
    for i, sz in enumerate(sizes):
        if sz <= 0:
            buffers.append(b'')
            continue

        if offset + sz > data_len:
            logger.debug(
                "BPGC bytecode buffer #%d: size=%d exceeds remaining %d bytes",
                i, sz, data_len - offset,
            )
            # 尝试读取剩余数据
            sz = data_len - offset
            if sz <= 0:
                break

        buf = data[offset:offset + sz]
        offset += sz

        # Validate buffer ends with expected sentinel (tolerant)
        if buf and buf[-1] not in (_END_OF_SCRIPT, _COOKED_END_SENTINEL):
            logger.debug(
                "Bytecode buffer #%d ends with 0x%02X, accepting in tolerant mode",
                i, buf[-1],
            )

        buffers.append(buf)

    return buffers


def extract_bpgc_bytecode(
    archive: FArchive,
    bpgc_export: ObjectExport,
    summary: PackageFileSummary,
    asset_name: str,
    name_map: list[str],
    import_map: list,
    export_map: list,
) -> dict[str, bytes]:
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
        Dict mapping function index (as string "0", "1", ...) to bytecode bytes.
        Empty dict if not a BPGC or no bytecode data.

    Raises:
        ParseError: If script region structure is invalid
    """
    from uasset_read.serializers.object_resources import detect_blueprint_generated_class
    from uasset_read.serializers.property_tags import read_property_tag
    from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION

    # Step 1: Validate BPGC export
    if not detect_blueprint_generated_class(bpgc_export, import_map, export_map):
        logger.debug("Export '%s' is not a BlueprintGeneratedClass, skipping", bpgc_export.object_name)
        return {}

    # Step 2: Check script_serialization
    if not bpgc_export.has_script_serialization:
        logger.debug("BPGC '%s' has no script_serial_region data", bpgc_export.object_name)
        return {}

    # Step 3: Calculate script start position
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        script_start = bpgc_export.serial_offset + bpgc_export.script_serialization_start_offset
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
        logger.debug("BPGC '%s': no bytecode data after PropertyTags", bpgc_export.object_name)
        return {}

    # 注意: script_serialization_size 仅覆盖 PropertyTags 区域，不包含字节码数据。
    # 字节码数据位于 serial region 的剩余部分（PropertyTags 之后）。

    raw_bytecode = archive.read_bytes(remaining_bytes)

    # Step 7: Parse cooked bytecode buffers
    buffers = _parse_cooked_bytecode_buffer(raw_bytecode)

    if not buffers:
        # #343: 区分"无字节码"和"解析失败"
        # 注意：remaining_bytes <= 0 的情况已在第 181-183 行处理
        logger.debug(
            "BPGC '%s': _parse_cooked_bytecode_buffer 返回空 (%d bytes 可用），"
            "可能是格式变体或数据损坏",
            asset_name, remaining_bytes,
        )
        return {}

    logger.info(
        "BPGC '%s': extracted %d bytecode buffers from script_serial_region",
        bpgc_export.object_name, len(buffers),
    )

    # Return dict mapping index string to bytecode bytes
    return {str(i): buf for i, buf in enumerate(buffers)}


def map_bytecode_to_functions(
    bytecode_buffers: dict[str, bytes],
    function_exports: list[ObjectExport],
    name_map: list[str],
    import_map: list,
    export_map: list,
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

    Returns:
        Dict mapping function_name to bytecode_bytes.
        Empty dict if no matching functions/buffers.
    """
    from uasset_read.serializers.object_resources import resolve_class_name

    # Step 2: Filter to Function-type exports only
    function_type_exports = [
        exp for exp in function_exports
        if resolve_class_name(exp.class_index, import_map, export_map) in ("Function", "UFunction")
    ]

    if not function_type_exports:
        logger.debug("No Function exports found in export table")
        return {}

    # Sort buffers by index key for deterministic ordinal pairing
    sorted_indices = sorted(bytecode_buffers.keys(), key=lambda k: int(k))
    buffer_list = [bytecode_buffers[i] for i in sorted_indices]

    buf_count = len(buffer_list)
    func_count = len(function_type_exports)

    # Step 5: Log warning on count mismatch
    if buf_count != func_count:
        logger.debug(
            "Bytecode/function count mismatch: %d buffers vs %d Function exports — "
            "mapping by min count",
            buf_count, func_count,
        )

    # Step 3: Pair by ordinal position
    pair_count = min(buf_count, func_count)
    result = {}
    for i in range(pair_count):
        func_export = function_type_exports[i]
        func_name = func_export.object_name
        result[func_name] = buffer_list[i]

    logger.info("Mapped %d bytecode buffers to Function exports", len(result))
    return result

