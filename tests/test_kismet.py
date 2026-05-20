"""
Kismet bytecode extractor and expression parser tests.

Tests for Phase 62: bytecode → expression tree.
"""
import logging
import pytest

from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.tokens import EExprToken
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.exceptions import ParseError


# ===========================================================================
# Task 1: FKismetArchive tolerant mode
# ===========================================================================


def test_fkismet_archive_tolerant_mode():
    """Test FKismetArchive tolerant parameter and unknown token handling."""
    name_map: list[str] = []

    # 1. Default: strict mode — unknown token raises ParseError
    # EX_EndOfScript (0x53) is known, so this should work
    strict_archive = FKismetArchive(b'\x53', "Test", name_map, tolerant=False)
    expr = strict_archive.read_expression()
    assert expr.Token == EExprToken.EX_EndOfScript
    assert isinstance(expr, KismetExpression)

    # 2. Strict mode: unknown token (0xFF = EX_Max) raises ParseError
    strict_archive = FKismetArchive(b'\xFF', "Test", name_map, tolerant=False)
    with pytest.raises(ParseError, match="Unknown EExprToken"):
        strict_archive.read_expression()

    # 3. Tolerant mode: unknown token is skipped, continues reading
    # Byte stream: [unknown 0xFF] + [EX_EndOfScript 0x53]
    tolerant_archive = FKismetArchive(b'\xFF\x53', "Test", name_map, tolerant=True)
    expr = tolerant_archive.read_expression()
    assert expr.Token == EExprToken.EX_EndOfScript

    # 4. Tolerant mode: 10 consecutive unknown tokens raises ParseError
    ten_unknowns = bytes([0xFF] * 10)
    tolerant_archive = FKismetArchive(ten_unknowns, "Test", name_map, tolerant=True)
    with pytest.raises(ParseError, match="Too many consecutive unknown tokens"):
        tolerant_archive.read_expression()

    # 5. Tolerant mode: unknown tokens followed by known token resets counter
    # Pattern: 9 unknowns + known + unknown (should not hit the 10-limit)
    mixed = bytes([0xFF] * 9) + b'\x53' + b'\xFF'
    tolerant_archive = FKismetArchive(mixed, "Test", name_map, tolerant=True)
    # Should successfully read EX_EndOfScript after skipping 9 unknowns
    expr = tolerant_archive.read_expression()
    assert expr.Token == EExprToken.EX_EndOfScript

    # 6. Existing non-tolerant behavior unchanged
    archive = FKismetArchive(b'\x53', "Test", name_map)  # default tolerant=False
    expr = archive.read_expression()
    assert expr.Token == EExprToken.EX_EndOfScript


# ===========================================================================
# Task 2: bytecode extractor
# ===========================================================================


def test_bytecode_extractor():
    """Test extract_bytecode_bytes and parse_bytecode_stream."""
    from uasset_read.kismet.bytecode_extractor import (
        extract_bytecode_bytes, parse_bytecode_stream, extract_and_parse, USTRUCT_TYPES
    )
    from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
    from uasset_read.serializers.package_summary import PackageFileSummary
    import io

    # 1. parse_bytecode_stream with empty bytes returns empty list
    assert parse_bytecode_stream(b'', []) == []

    # 2. parse_bytecode_stream with valid bytecode
    # EX_EndOfScript (0x53) is a valid single-expression stream
    exprs = parse_bytecode_stream(b'\x53', [])
    assert len(exprs) == 1
    assert exprs[0].Token == EExprToken.EX_EndOfScript

    # 3. parse_bytecode_stream with tolerant mode
    # Unknown token + known token
    exprs = parse_bytecode_stream(b'\xFF\x53', [], tolerant=True)
    assert len(exprs) == 1
    assert exprs[0].Token == EExprToken.EX_EndOfScript

    # 4. USTRUCT_TYPES whitelist check
    assert "Function" in USTRUCT_TYPES
    assert "UFunction" in USTRUCT_TYPES
    assert "K2Node_FunctionEntry" in USTRUCT_TYPES
    assert "K2Node_FunctionResult" in USTRUCT_TYPES


# ===========================================================================
# Task 4: output formats
# ===========================================================================


def test_expression_output_formats():
    """Test expressions_to_flat_list and expressions_to_tree."""
    pass


# ===========================================================================
# Task 5: integration tests
# ===========================================================================


def test_extract_bytecode_from_uasset():
    """End-to-end: extract bytecode from real .uasset file."""
    pass


def test_parse_bytecode_to_expressions():
    """End-to-end: parse bytecode to expression list."""
    pass


def test_tolerant_mode_vs_strict_mode():
    """Compare tolerant vs strict mode on malformed bytecode."""
    pass
