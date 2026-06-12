"""
BPGC Bytecode Extraction — BlueprintGeneratedClass cooked bytecode parsing.

Extract bytecode from BPGC script_serial_region (fallback
for UE5 cooked Blueprints where Function exports contain no bytecode).

Provides:
- extract_bpgc_bytecode: Read BPGC script region, parse cooked format into per-function buffers
- map_bytecode_to_functions: Map bytecode buffers to Function exports by ordinal position
- _parse_cooked_bytecode_buffer: Pure logic function for buffer splitting
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from uasset_read.exceptions import ParseError
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary


logger = logging.getLogger(__name__)

# Cooked bytecode end-of-function sentinel variants
_END_OF_SCRIPT = 0x53        # EX_EndOfScript — standard
_COOKED_END_SENTINEL = 0xDD  # Cooked format variant seen in some UE5 assets


def _find_next_sentinel(data: bytes, start: int) -> int:
    """在 data 中查找下一个 EX_EndOfScript 或 0xDD 标记。"""
    for i in range(start, len(data)):
        if data[i] in (_END_OF_SCRIPT, _COOKED_END_SENTINEL):
            return i
    return len(data)


def _parse_cooked_bytecode_buffer(data: bytes) -> list[bytes]:
    """Parse raw BPGC script region bytes into per-function bytecode buffers.

    Cooked format: sequence of [u32 size][size bytes of bytecode], where each
    bytecode buffer should end with EX_EndOfScript (0x53) or cooked variant (0xDD).

    Pure logic function — no archive or I/O dependency.

    Args:
        data: Raw script_serial_region content (after PropertyTags + optional headers)

    Returns:
        List of bytecode buffers, one per function

    Stops on:
        - size == 0
        - size exceeding remaining bytes
        - no more data
    """
    buffers: list[bytes] = []
    offset = 0
    data_len = len(data)

    while offset < data_len:
        # Need at least 4 bytes for size prefix
        if offset + 4 > data_len:
            break

        # Read u32 size (little-endian, matching UE FArchive format)
        size = int.from_bytes(data[offset:offset + 4], byteorder='little', signed=False)
        offset += 4

        # 容错处理 - 如果 size 不合理，尝试跳过
        if size == 0 or size > (data_len - offset):
            next_sentinel = _find_next_sentinel(data, offset - 4)
            if next_sentinel > offset + 3:
                offset = next_sentinel - 3
                continue
            break

        buf = data[offset:offset + size]
        offset += size

        # Validate buffer ends with expected sentinel (tolerant)
        if buf and buf[-1] not in (_END_OF_SCRIPT, _COOKED_END_SENTINEL):
            logger.warning(
                "Bytecode buffer #%d ends with 0x%02X, accepting in tolerant mode",
                len(buffers), buf[-1],
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
        if tag.name == "None":
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
        logger.warning("BPGC '%s': no bytecode data after PropertyTags", bpgc_export.object_name)
        return {}

    if remaining_bytes > bpgc_export.script_serialization_size:
        # Clamp to script_serial_region bounds
        remaining_bytes = bpgc_export.script_serialization_size - (current_pos - script_start)
        if remaining_bytes <= 0:
            return {}

    raw_bytecode = archive.read_bytes(remaining_bytes)

    # Step 7: Parse cooked bytecode buffers
    buffers = _parse_cooked_bytecode_buffer(raw_bytecode)

    if not buffers:
        logger.warning(
            "BPGC '%s': parsed 0 bytecode buffers from %d bytes",
            bpgc_export.object_name, len(raw_bytecode),
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
        logger.warning(
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

