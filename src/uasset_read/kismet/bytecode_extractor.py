"""
Kismet Bytecode Extractor — UStruct ScriptBytecode extraction and parsing.

Bridge between FKismetArchive and AST translation.

Provides:
- extract_bytecode_bytes: Extract raw ScriptBytecode from a UStruct export
- parse_bytecode_stream: Parse bytecode bytes into KismetExpression list
- extract_and_parse: Combined extraction + parsing entry point
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.exceptions import ParseError
from uasset_read.constants import UE_NONE_SENTINEL

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary


logger = logging.getLogger(__name__)

_PLAUSIBLE_SCRIPT_START_TOKENS = {
    0x04,  # EX_Return
    0x19,  # EX_Context
    0x1B,  # EX_VirtualFunction
    0x1C,  # EX_FinalFunction
    0x46,  # EX_LocalFinalFunction
}

# ===========================================================================
# Function export class whitelist — only true Function/UFunction exports
# ===========================================================================

FUNCTION_EXPORT_CLASSES = frozenset({"Function", "UFunction"})

# ---------------------------------------------------------------------------
# False positive data detection (#424)
# ---------------------------------------------------------------------------


def _has_false_positive_pattern(data: bytes) -> bool:
    """Detect false positive data patterns: too many consecutive constant tokens or repeated byte patterns.

    Used by diagnostic scanning to filter candidates that are clearly non-code
    segments using statistical characteristics.
    """
    if len(data) < 4:
        return False
    # Detect consecutive IntConst (0x1D) followed by 4-byte integer patterns
    int_const_count = sum(1 for i in range(len(data) - 5) if data[i] == 0x1D)
    if int_const_count > 3:
        return True
    # Detect if more than 50% of bytes are the same value (false positive characteristic)
    from collections import Counter
    most_common_count = Counter(data).most_common(1)[0][1]
    if most_common_count / len(data) > 0.5:
        return True
    return False


# Scan complexity limits — prevent combinatorial explosion in large Blueprints
_MAX_SCAN_ATTEMPTS = 500       # Maximum (start, end) combinations to try per function
_MAX_CANDIDATE_SIZE = 4096     # Maximum candidate byte stream length (bytes)



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
) -> tuple[bytes | None, str, int]:
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
        Tuple of (bytecode_bytes, fallback_reason, bytecode_buffer_size).
        fallback_reason is one of: "function_export", "none"
        bytecode_buffer_size is the declared logical buffer size (0 when unavailable)

    Raises:
        ParseError: If serializedScriptSize is out of bounds
    """
    from uasset_read.serializers.object_resources import resolve_class_name
    from uasset_read.serializers.property_tags import read_property_tag
    from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION

    # T-62-01: Verify class is in UStruct whitelist
    class_name = resolve_class_name(export.class_index, import_map, export_map)
    if class_name not in FUNCTION_EXPORT_CLASSES:
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
        tag = read_property_tag(archive, name_map)
        if tag.name == UE_NONE_SENTINEL:
            break
        archive.skip(tag.size)

    # Read bytecode header: bytecodeBufferSize + serializedScriptSize
    bytecode_buffer_size = archive.read_i32()
    serialized_script_size = archive.read_i32()

    # T-62-02: Validate serializedScriptSize bounds
    if serialized_script_size <= 0:
        return None, "none"

    if serialized_script_size > export.script_serialization_size:
        raise ParseError(
            f"serializedScriptSize ({serialized_script_size}) exceeds "
            f"script_serialization_size ({export.script_serialization_size}) for '{export.object_name}'"
        )

    return archive.read_bytes(serialized_script_size), "function_export", bytecode_buffer_size


# ===========================================================================
# Bytecode parsing
# ===========================================================================


def parse_bytecode_stream(
    bytecode_bytes: bytes,
    name_map: list[str],
    summary: "PackageFileSummary | None" = None,
    *,
    bytecode_buffer_size: int = 0,
    tolerant: bool = False,
) -> list[KismetExpression]:
    """
    Parse raw bytecode bytes into a list of KismetExpression trees.

    Stops immediately after EX_EndOfScript and validates script closure invariants:
    - All serialized bytes consumed (serialized_offset == len(bytecode_bytes))
    - Logical cursor equals declared buffer size (bytecode_index == bytecode_buffer_size)
    - Last top-level token is EX_EndOfScript
    - All absolute jump targets are valid top-level StatementIndex values

    Args:
        bytecode_bytes: Raw ScriptBytecode data
        name_map: Name table for expression resolution
        summary: PackageFileSummary for LWC version checks (optional)
        bytecode_buffer_size: Declared logical bytecode buffer size (0 = skip logical validation)
        tolerant: If True, skip unknown tokens instead of raising ParseError

    Returns:
        List of KismetExpression (last element is EX_EndOfScript)

    Raises:
        ParseError: On closure invariant violations or invalid jump targets
    """
    from uasset_read.kismet.tokens import EExprToken as _EExprToken

    if not bytecode_bytes:
        if bytecode_buffer_size != 0:
            raise ParseError(
                f"Bytecode size mismatch: logical index 0, expected {bytecode_buffer_size}"
            )
        return []

    archive = FKismetArchive(bytecode_bytes, "ScriptBytecode", name_map, tolerant=tolerant)
    archive.bytecode_buffer_size = bytecode_buffer_size
    if summary is not None:
        archive.summary = summary
    expressions: list[KismetExpression] = []

    while archive.tell() < len(bytecode_bytes):
        expr = archive.read_expression()
        expressions.append(expr)
        if expr.Token == _EExprToken.EX_EndOfScript:
            break

    # --- Closure invariant checks ---
    if not expressions or expressions[-1].Token != _EExprToken.EX_EndOfScript:
        raise ParseError("Missing EX_EndOfScript at end of script")

    if archive.serialized_offset != len(bytecode_bytes):
        raise ParseError(
            f"Serialized size mismatch: consumed {archive.serialized_offset} bytes, "
            f"expected {len(bytecode_bytes)}"
        )

    if bytecode_buffer_size > 0 and archive.bytecode_index != bytecode_buffer_size:
        raise ParseError(
            f"Bytecode size mismatch: logical index {archive.bytecode_index}, "
            f"expected {bytecode_buffer_size}"
        )

    # --- Jump target validation ---
    _validate_jump_targets(expressions)

    return expressions


def _validate_jump_targets(expressions: list[KismetExpression]) -> None:
    """Validate that all absolute jump targets are valid top-level StatementIndex values.

    Checks EX_Jump, EX_JumpIfNot, EX_PushExecutionFlow, EX_SwitchValue, and
    EX_AutoRtfmTransact targets.
    """
    from uasset_read.kismet.tokens import EExprToken as _EExprToken

    top_level_indices = {expr.StatementIndex for expr in expressions}

    for expr in expressions:
        targets: list[int] = []

        if expr.Token in (_EExprToken.EX_Jump, _EExprToken.EX_JumpIfNot, _EExprToken.EX_Skip):
            targets.append(expr.CodeOffset)
        elif expr.Token == _EExprToken.EX_PushExecutionFlow:
            targets.append(expr.PushingAddress)
        elif expr.Token == _EExprToken.EX_SwitchValue:
            targets.append(expr.EndGotoOffset)
            for case in (expr.Cases or []):
                targets.append(case.NextOffset)
        elif expr.Token == _EExprToken.EX_AutoRtfmTransact:
            targets.append(expr.CodeOffset)

        for target in targets:
            if target not in top_level_indices:
                raise ParseError(
                    f"Invalid jump target {target} at offset {expr.StatementIndex}"
                )


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
    # Check if this is a Function/UFunction type
    from uasset_read.serializers.object_resources import resolve_class_name

    class_name = resolve_class_name(export.class_index, import_map, export_map)
    if class_name not in FUNCTION_EXPORT_CLASSES:
        return ([], None, "none")

    try:
        bytecode_bytes, fallback_reason, bytecode_buffer_size = extract_bytecode_bytes(
            archive, export, summary, name_map, import_map, export_map
        )
    except ParseError as e:
        return ([], str(e), "none")

    if bytecode_bytes is None:
        return ([], None, fallback_reason)

    try:
        expressions = parse_bytecode_stream(
            bytecode_bytes, name_map, summary,
            bytecode_buffer_size=bytecode_buffer_size, tolerant=tolerant,
        )
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
        except AttributeError:
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
