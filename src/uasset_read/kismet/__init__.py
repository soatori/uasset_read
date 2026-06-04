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
    reset_bpgc_cache,
)

# C++ pseudocode translator
from uasset_read.kismet.translator import (
    KismetTranslator, MathFunctionCleaner, TypeRegistry, line_cpp, UE_TYPE_MAP,
)
from uasset_read.kismet.body_builder import FunctionBodyBuilder, to_function_body
from uasset_read.kismet.structured_flow import StructuredControlFlow, StructuredBlock
from uasset_read.kismet.blueprint_node_cleaner import BlueprintNodeCleaner

# Decompilation result and pipeline
from uasset_read.kismet.result import KismetDecompiledResult
from uasset_read.kismet.pipeline import decompile_uasset, decompile_single_function

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
    "reset_bpgc_cache",
    # C++ translator
    "KismetTranslator",
    "MathFunctionCleaner",
    "TypeRegistry",
    "line_cpp",
    "UE_TYPE_MAP",
    "FunctionBodyBuilder",
    "to_function_body",
    "StructuredControlFlow",
    "StructuredBlock",
    # Blueprint node cleaner
    "BlueprintNodeCleaner",
    # Decompilation result and pipeline
    "KismetDecompiledResult",
    "decompile_uasset",
    "decompile_single_function",
]
