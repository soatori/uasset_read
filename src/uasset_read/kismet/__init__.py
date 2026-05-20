"""Kismet bytecode expression system -- EExprToken + KismetExpression class hierarchy + FKismetArchive."""
from __future__ import annotations

from uasset_read.kismet.tokens import (
    EExprToken, ECastToken, EScriptInstrumentationType,
    EBlueprintTextLiteralType, EAutoRtfmStopTransactMode,
)
from uasset_read.kismet.expressions.base import KismetExpression, KismetExpressionT
from uasset_read.kismet.expressions import EXPR_CLASS_MAP
from uasset_read.kismet.property_pointer import FKismetPropertyPointer, FFieldPath

from uasset_read.kismet.archive import FKismetArchive

from uasset_read.kismet.bytecode_extractor import (
    extract_bytecode_bytes, parse_bytecode_stream, extract_and_parse, USTRUCT_TYPES,
)

__all__ = [
    "EExprToken",
    "ECastToken",
    "EScriptInstrumentationType",
    "EBlueprintTextLiteralType",
    "EAutoRtfmStopTransactMode",
    "KismetExpression",
    "KismetExpressionT",
    "EXPR_CLASS_MAP",
    "FKismetPropertyPointer",
    "FFieldPath",
    "FKismetArchive",
    # Bytecode extractor
    "extract_bytecode_bytes",
    "parse_bytecode_stream",
    "extract_and_parse",
    "USTRUCT_TYPES",
]
