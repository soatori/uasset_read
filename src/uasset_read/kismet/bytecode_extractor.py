"""
Kismet Bytecode Extractor — UStruct ScriptBytecode extraction and parsing.

Bridge between FKismetArchive and AST translation.
BPGC fallback for UE5 cooked Blueprints.

Provides:
- extract_bytecode_bytes: Extract raw ScriptBytecode from a UStruct export (with BPGC fallback)
- parse_bytecode_stream: Parse bytecode bytes into KismetExpression list
- extract_and_parse: Combined extraction + parsing entry point
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.exceptions import ParseError

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary


logger = logging.getLogger(__name__)

# Module-level BPGC bytecode cache (populated on first fallback, keyed by function name)
# T-72C-04 mitigation: cache is per-module but reset at each decompile_uasset() call context
_bpgc_bytecode_cache: dict[str, bytes] | None = None

_PLAUSIBLE_SCRIPT_START_TOKENS = {
    0x04,  # EX_Return
    0x19,  # EX_Context
    0x1B,  # EX_VirtualFunction
    0x1C,  # EX_FinalFunction
    0x46,  # EX_LocalFinalFunction
    # 已移除 0x1D (EX_IntConst)、0x5A (EX_WireTracepoint)、0x5E (EX_Tracepoint)
    # 这些 token 频繁出现在内嵌数据中，导致 scanner 误选起始位置，
    # 产生裸数字（如 1509949440）等错误反编译输出。
}

# 扫描复杂度限制 — 防止大型蓝图组合爆炸导致超时
_MAX_SCAN_ATTEMPTS = 500       # 单个函数最多尝试的 (start, end) 组合数
_MAX_CANDIDATE_SIZE = 4096     # 单个候选字节流最大长度（字节）


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
) -> tuple[bytes | None, str]:
    """
    Extract ScriptBytecode raw bytes from a UStruct export.

    Strategy: Navigate to the export's property region, skip PropertyTags
    until "None", then read bytecodeBufferSize + serializedScriptSize header,
    and return the bytecode data.

    Per UStruct.cs, ScriptBytecode is NOT a PropertyTag value —
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
        Tuple of (bytecode_bytes, fallback_reason).
        fallback_reason is one of: "function_export", "bpgc_bytecode_extraction",
        "serial_scan_recovery", "none"

    Raises:
        ParseError: If serializedScriptSize is out of bounds
    """
    from uasset_read.serializers.object_resources import resolve_class_name
    from uasset_read.serializers.property_tags import read_property_tag
    from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION

    # T-62-01: Verify class is in UStruct whitelist
    class_name = resolve_class_name(export.class_index, import_map, export_map)
    if class_name not in USTRUCT_TYPES:
        return None, "none"

    # No script data
    if not export.has_script_serialization:
        return None, "none"

    # Calculate script start position
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        script_start = export.serial_offset + export.script_serialization_start_offset
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
        tag = read_property_tag(archive, name_map, summary=summary)
        if tag.name == "None":
            break
        archive.skip(tag.size)

    # Read bytecode header: bytecodeBufferSize + serializedScriptSize
    bytecode_buffer_size = archive.read_i32()
    serialized_script_size = archive.read_i32()

    # T-62-02: Validate serializedScriptSize bounds
    if serialized_script_size <= 0:
        # BPGC fallback for UE5 cooked Blueprints
        fallback = _bpgc_fallback(
            archive, export, summary, name_map, import_map, export_map
        )
        if fallback is not None:
            return fallback, "bpgc_bytecode_extraction"
        result = _scan_export_serial_for_bytecode(
            archive, export, name_map, tolerant=getattr(archive, "_tolerant", False)
        )
        reason = "serial_scan_recovery" if result is not None else "none"
        return result, reason

    if serialized_script_size > export.script_serialization_size:
        raise ParseError(
            f"serializedScriptSize ({serialized_script_size}) exceeds "
            f"script_serialization_size ({export.script_serialization_size}) for '{export.object_name}'"
        )

    return archive.read_bytes(serialized_script_size), "function_export"


def _scan_export_serial_for_bytecode(
    archive: FArchive,
    export: ObjectExport,
    name_map: list[str],
    tolerant: bool = True,
) -> bytes | None:
    """Best-effort recovery for cooked Function exports with inline bytecode.

    Some UE5 cooked assets report a tiny script_serial_size while the serialized
    Function body still contains a compact bytecode suffix. When the normal
    UStruct path and BPGC fallback both fail, scan the export serial bytes for a
    parseable expression stream ending in EX_EndOfScript.

    Complexity guards: _MAX_SCAN_ATTEMPTS caps total (start, end) pairs,
    _MAX_CANDIDATE_SIZE caps each candidate's byte length.
    """
    original_pos = archive.tell()
    try:
        archive.seek(export.serial_offset)
        data = archive.read_bytes(export.serial_size)
    finally:
        archive.seek(original_pos)

    best: tuple[int, bytes] | None = None
    end_positions = [idx for idx, b in enumerate(data) if b == 0x53]
    attempts = 0
    for start, first in enumerate(data):
        if first not in _PLAUSIBLE_SCRIPT_START_TOKENS:
            continue
        for end in end_positions:
            if end < start:
                continue
            candidate = data[start:end + 1]
            if len(candidate) < 2:
                continue
            if len(candidate) > _MAX_CANDIDATE_SIZE:
                # Larger candidates are unlikely; skip further end positions
                break
            attempts += 1
            if attempts > _MAX_SCAN_ATTEMPTS:
                logger.debug(
                    "Scan bytecode for '%s': hit _MAX_SCAN_ATTEMPTS (%d), stopping",
                    export.object_name, _MAX_SCAN_ATTEMPTS,
                )
                return best[1] if best else None
            try:
                expressions = parse_bytecode_stream(candidate, name_map, tolerant=tolerant)
            except Exception:
                continue
            if not expressions:
                continue
            last = type(expressions[-1]).__name__
            if last != "EX_EndOfScript":
                continue
            score = len(expressions)
            if best is None or score > best[0]:
                best = (score, candidate)
            break

    if best is None:
        return None
    logger.warning(
        "Recovered bytecode for '%s' by scanning Function serial (%d expressions)",
        export.object_name, best[0],
    )
    return best[1]


def _bpgc_fallback(
    archive: FArchive,
    export: ObjectExport,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list,
    export_map: list,
) -> bytes | None:
    """
    BPGC bytecode fallback for UE5 cooked Blueprints.

    When Function exports have no bytecode in their script_serial_region,
    fall back to extracting bytecode from the BlueprintGeneratedClass export.

    Uses module-level cache to avoid re-extracting for each function.

    Args:
        archive: FArchive instance (file-level archive)
        export: ObjectExport for the Function
        summary: PackageFileSummary for version info
        name_map: Name table for PropertyTag parsing
        import_map: Import table for class resolution
        export_map: Export table for class resolution

    Returns:
        Bytecode bytes for the function, or None if not found.

    T-72C-03 mitigation: wrapped in try/except, returns None on failure.
    """
    global _bpgc_bytecode_cache

    from uasset_read.kismet.bpgc_bytecode import (
        extract_bpgc_bytecode,
        map_bytecode_to_functions,
    )
    from uasset_read.serializers.object_resources import find_main_blueprint_generated_class
    import os

    # Derive asset name from archive filename
    asset_name = os.path.splitext(os.path.basename(archive._path))[0]

    # Populate cache on first fallback call
    if _bpgc_bytecode_cache is None:
        logger.debug(
            "Falling back to BPGC bytecode extraction for '%s'",
            export.object_name,
        )

        try:
            # Find main BlueprintGeneratedClass export
            bpgc_export = find_main_blueprint_generated_class(
                export_map, import_map, asset_name
            )

            if bpgc_export is None:
                logger.debug("No BlueprintGeneratedClass found for '%s'", asset_name)
                _bpgc_bytecode_cache = {}  # Empty cache to prevent re-search
                return None

            # Extract all bytecode buffers from BPGC
            bytecode_buffers = extract_bpgc_bytecode(
                archive, bpgc_export, summary, asset_name, name_map, import_map, export_map
            )

            if not bytecode_buffers:
                logger.debug("No bytecode buffers extracted from BPGC '%s'", bpgc_export.object_name)
                _bpgc_bytecode_cache = {}
                return None

            # Map buffers to Function exports by name
            _bpgc_bytecode_cache = map_bytecode_to_functions(
                bytecode_buffers, export_map, name_map, import_map, export_map
            )

            logger.info(
                "BPGC fallback: cached %d function bytecode mappings from '%s'",
                len(_bpgc_bytecode_cache), bpgc_export.object_name,
            )

        except Exception as e:
            # T-72C-03: Return None on failure rather than raising
            logger.error("BPGC bytecode extraction failed: %s", e)
            _bpgc_bytecode_cache = {}
            return None

    # Look up function name in cache
    func_name = export.object_name
    if func_name in _bpgc_bytecode_cache:
        return _bpgc_bytecode_cache[func_name]

    logger.debug("Function '%s' not found in BPGC bytecode cache", func_name)
    return None


def reset_bpgc_cache() -> None:
    """
    Reset the BPGC bytecode cache for a new decompile_uasset() call.

    Called by decompile_uasset() at the start of each invocation to ensure
    fresh cache per file (T-72C-04 mitigation).
    """
    global _bpgc_bytecode_cache
    _bpgc_bytecode_cache = None
    # 同时重置 FKismetArchive 的警告去重集合
    from uasset_read.kismet.archive import FKismetArchive
    FKismetArchive.reset_warned_offsets()


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
    UStruct.Deserialize() behavior. EX_EndOfScript will naturally
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
) -> tuple[list[KismetExpression], str | None, str]:
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
        Tuple of (expressions, error_message, fallback_reason).
        - On success: (list[KismetExpression], None, reason)
        - On non-UStruct or no bytecode: ([], None, "none")
        - On ParseError: ([], str(error), "none")
    """
    # Check if this is a UStruct type
    from uasset_read.serializers.object_resources import resolve_class_name

    class_name = resolve_class_name(export.class_index, import_map, export_map)
    if class_name not in USTRUCT_TYPES:
        return ([], None, "none")

    try:
        bytecode_bytes, fallback_reason = extract_bytecode_bytes(
            archive, export, summary, name_map, import_map, export_map
        )
    except ParseError as e:
        return ([], str(e), "none")

    if bytecode_bytes is None:
        return ([], None, fallback_reason)

    try:
        expressions = parse_bytecode_stream(bytecode_bytes, name_map, tolerant=tolerant)
        return (expressions, None, fallback_reason)
    except ParseError as e:
        return ([], str(e), fallback_reason)


# ===========================================================================
# Output formatting (BYTECODE-03)
# ===========================================================================


def _is_kismet_expression(obj: object) -> bool:
    """Check if obj is a KismetExpression (avoids circular import)."""
    return isinstance(obj, KismetExpression)


def _expr_to_tree_node(expr: KismetExpression) -> dict:
    """Convert a single KismetExpression to a tree node dict with children."""
    node_dict = expr.to_dict()
    result = {
        "StatementIndex": expr.StatementIndex,
        "Token": expr.Token.name if hasattr(expr.Token, 'name') else str(expr.Token),
        "type": type(expr).__name__,
    }

    children = []
    # Scan to_dict() values and any extra attributes for nested expressions
    for key, val in node_dict.items():
        if _is_kismet_expression(val):
            children.append({
                "key": key,
                **_expr_to_tree_node(val),
            })
        elif isinstance(val, list):
            for i, item in enumerate(val):
                if _is_kismet_expression(item):
                    children.append({
                        "key": key,
                        "index": i,
                        **_expr_to_tree_node(item),
                    })

    # Also scan instance attributes for nested expressions not in to_dict()
    for key in dir(expr):
        if key.startswith('_') or key in ('Token', 'StatementIndex', 'to_dict'):
            continue
        try:
            val = getattr(expr, key)
        except Exception:
            continue
        if _is_kismet_expression(val):
            # Avoid duplicates if already in node_dict
            if not any(c.get('key') == key for c in children):
                children.append({
                    "key": key,
                    **_expr_to_tree_node(val),
                })
        elif isinstance(val, list):
            for i, item in enumerate(val):
                if _is_kismet_expression(item):
                    if not any(c.get('key') == key and c.get('index') == i for c in children):
                        children.append({
                            "key": key,
                            "index": i,
                            **_expr_to_tree_node(item),
                        })

    if children:
        result["children"] = children

    return result


def expressions_to_flat_list(expressions: list[KismetExpression]) -> list[dict]:
    """
    Convert expression list to flat dict list.

    Each dict contains: StatementIndex, Token (name), type (class name),
    plus any additional fields from to_dict().

    Does NOT recurse into nested child expressions.
    """
    result = []
    for expr in expressions:
        item = {
            "StatementIndex": expr.StatementIndex,
            "Token": expr.Token.name if hasattr(expr.Token, 'name') else str(expr.Token),
            "type": type(expr).__name__,
        }
        item.update(expr.to_dict())
        result.append(item)
    return result


def expressions_to_tree(expressions: list[KismetExpression]) -> list[dict]:
    """
    Convert expression list to tree structure with children.

    Each dict contains: StatementIndex, Token, type, children (nested
    sub-expressions). Recursively processes nested KismetExpression
    instances found as attributes or in to_dict() values.
    """
    return [_expr_to_tree_node(expr) for expr in expressions]
