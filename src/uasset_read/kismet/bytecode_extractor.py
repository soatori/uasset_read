"""
Kismet Bytecode Extractor — bytecode parsing and expression tree construction.

Provides:
- parse_bytecode_stream: Parse bytecode bytes into KismetExpression list
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.exceptions import ParseError

if TYPE_CHECKING:
    from uasset_read.serializers.package_summary import PackageFileSummary


logger = logging.getLogger(__name__)

# ===========================================================================
# Function export class whitelist — only true Function/UFunction exports
# ===========================================================================

FUNCTION_EXPORT_CLASSES = frozenset({"Function", "UFunction"})


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
            raise ParseError(f"Bytecode size mismatch: logical index 0, expected {bytecode_buffer_size}")
        return []

    archive = FKismetArchive(bytecode_bytes, "ScriptBytecode", name_map, tolerant=tolerant)
    archive.bytecode_buffer_size = bytecode_buffer_size
    if summary is not None:
        archive.summary = summary
        from uasset_read.kismet.ufunction_reader import (
            FORTNITE_GUID,
            RELEASE_GUID,
            get_kismet_custom_version,
        )

        archive.fortnite_version = get_kismet_custom_version(summary, FORTNITE_GUID)
        archive.release_version = get_kismet_custom_version(summary, RELEASE_GUID)
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
            f"Serialized size mismatch: consumed {archive.serialized_offset} bytes, expected {len(bytecode_bytes)}"
        )

    if bytecode_buffer_size > 0 and archive.bytecode_index != bytecode_buffer_size:
        raise ParseError(
            f"Bytecode size mismatch: logical index {archive.bytecode_index}, expected {bytecode_buffer_size}"
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
            for case in expr.Cases or []:
                targets.append(case.NextOffset)
        elif expr.Token == _EExprToken.EX_AutoRtfmTransact:
            targets.append(expr.CodeOffset)

        for target in targets:
            if target not in top_level_indices:
                raise ParseError(f"Invalid jump target {target} at offset {expr.StatementIndex}")


# ===========================================================================
# Output formatting (BYTECODE-03)
# ===========================================================================
