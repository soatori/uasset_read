"""
Kismet Bytecode Extractor — UStruct ScriptBytecode extraction and parsing.

Phase 62: Bridge between Phase 61 (FKismetArchive) and Phase 63 (AST translation).

Provides:
- extract_bytecode_bytes: Extract raw ScriptBytecode from a UStruct export
- parse_bytecode_stream: Parse bytecode bytes into KismetExpression list
- extract_and_parse: Combined extraction + parsing entry point
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.exceptions import ParseError

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary


# ===========================================================================
# UStruct type whitelist (per D-01, T-62-01 mitigation)
# ===========================================================================

USTRUCT_TYPES = frozenset([
    "Function", "UFunction",
    "K2Node_FunctionEntry", "K2Node_FunctionResult",
])


# ===========================================================================
# Bytecode extraction
# ===========================================================================


def extract_bytecode_bytes(
    archive: FArchive,
    export: ObjectExport,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list,
    export_map: list,
) -> bytes | None:
    """
    Extract ScriptBytecode raw bytes from a UStruct export.

    Strategy: Navigate to the export's property region, skip PropertyTags
    until "None", then read bytecodeBufferSize + serializedScriptSize header,
    and return the bytecode data.

    Per CUE4Parse UStruct.cs, ScriptBytecode is NOT a PropertyTag value —
    it is embedded directly in the UStruct serialization stream AFTER the
    PropertyTag loop.

    Args:
        archive: FArchive instance (file-level archive)
        export: ObjectExport to extract bytecode from
        summary: PackageFileSummary for version flags
        name_map: Name table for PropertyTag parsing
        import_map: Import table for class name resolution
        export_map: Export table for class name resolution

    Returns:
        Raw bytecode bytes, or None if export has no bytecode

    Raises:
        ParseError: If serializedScriptSize is out of bounds
    """
    from uasset_read.serializers.object_resources import resolve_class_name
    from uasset_read.serializers.property_tags import read_property_tag
    from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION

    # T-62-01: Verify class is in UStruct whitelist
    class_name = resolve_class_name(export.class_index, import_map, export_map)
    if class_name not in USTRUCT_TYPES:
        return None

    # No script data
    if export.script_serial_size <= 0:
        return None

    # Calculate script start position
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        script_start = export.serial_offset + export.script_serial_offset
    else:
        script_start = export.serial_offset

    archive.seek(script_start)

    # T-62-02: SerializationControlExtensions header
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        ctrl = archive.read_u8()
        if ctrl & 0x02:
            archive.read_u8()  # skip overridden operation

    # Skip PropertyTags until "None" (positions us at bytecode header)
    while True:
        tag = read_property_tag(archive, name_map)
        if tag.name == "None":
            break
        archive.skip(tag.size)

    # Read bytecode header: bytecodeBufferSize + serializedScriptSize
    bytecode_buffer_size = archive.read_i32()
    serialized_script_size = archive.read_i32()

    # T-62-02: Validate serializedScriptSize bounds
    if serialized_script_size <= 0:
        return None

    if serialized_script_size > export.script_serial_size:
        raise ParseError(
            f"serializedScriptSize ({serialized_script_size}) exceeds "
            f"script_serial_size ({export.script_serial_size}) for '{export.object_name}'"
        )

    return archive.read_bytes(serialized_script_size)


# ===========================================================================
# Bytecode parsing
# ===========================================================================


def parse_bytecode_stream(
    bytecode_bytes: bytes,
    name_map: list[str],
    tolerant: bool = False,
) -> list[KismetExpression]:
    """
    Parse raw bytecode bytes into a list of KismetExpression trees.

    Uses stream exhaustion (position < length) as loop terminator, matching
    CUE4Parse UStruct.Deserialize() behavior. EX_EndOfScript will naturally
    be the last expression read.

    Args:
        bytecode_bytes: Raw ScriptBytecode data
        name_map: Name table for expression resolution
        tolerant: If True, skip unknown tokens instead of raising ParseError

    Returns:
        List of KismetExpression (may include EX_EndOfScript as last element)
    """
    if not bytecode_bytes:
        return []

    archive = FKismetArchive(bytecode_bytes, "ScriptBytecode", name_map, tolerant=tolerant)
    expressions: list[KismetExpression] = []

    while archive.tell() < len(bytecode_bytes):
        expr = archive.read_expression()
        expressions.append(expr)

    return expressions


# ===========================================================================
# Combined extraction + parsing
# ===========================================================================


def extract_and_parse(
    archive: FArchive,
    export: ObjectExport,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list,
    export_map: list,
    tolerant: bool = False,
) -> tuple[list[KismetExpression], str | None]:
    """
    Extract ScriptBytecode from a UStruct export and parse into expressions.

    Convenience function combining extract_bytecode_bytes + parse_bytecode_stream.

    Args:
        archive: FArchive instance (file-level archive)
        export: ObjectExport to extract bytecode from
        summary: PackageFileSummary for version flags
        name_map: Name table for expression resolution
        import_map: Import table for class name resolution
        export_map: Export table for class name resolution
        tolerant: If True, use tolerant mode for FKismetArchive

    Returns:
        Tuple of (expressions, error_message).
        - On success: (list[KismetExpression], None)
        - On non-UStruct or no bytecode: ([], None)
        - On ParseError: ([], str(error))
    """
    # Check if this is a UStruct type
    from uasset_read.serializers.object_resources import resolve_class_name

    class_name = resolve_class_name(export.class_index, import_map, export_map)
    if class_name not in USTRUCT_TYPES:
        return ([], None)

    try:
        bytecode_bytes = extract_bytecode_bytes(
            archive, export, summary, name_map, import_map, export_map
        )
    except ParseError as e:
        return ([], str(e))

    if bytecode_bytes is None:
        return ([], None)

    try:
        expressions = parse_bytecode_stream(bytecode_bytes, name_map, tolerant=tolerant)
        return (expressions, None)
    except ParseError as e:
        return ([], str(e))
