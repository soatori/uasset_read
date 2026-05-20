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
    from uasset_read.kismet.bytecode_extractor import (
        parse_bytecode_stream, expressions_to_flat_list, expressions_to_tree,
    )
    import json

    # Create a simple expression list: EX_Return(EX_IntConst(42)) + EX_EndOfScript
    # EX_Return reads: expression (the return value)
    # Bytecode for EX_Return(0x04) + EX_IntConst(0x1D) + int32(42) + EX_EndOfScript(0x53)
    bytecode = b'\x04\x1D' + (42).to_bytes(4, 'little') + b'\x53'
    exprs = parse_bytecode_stream(bytecode, [])

    # 1. expressions_to_flat_list returns flat dict list
    flat = expressions_to_flat_list(exprs)
    assert isinstance(flat, list)
    assert len(flat) > 0
    for item in flat:
        assert 'StatementIndex' in item
        assert 'Token' in item
        assert 'type' in item

    # 2. expressions_to_tree returns tree with children
    tree = expressions_to_tree(exprs)
    assert isinstance(tree, list)
    assert len(tree) > 0
    # EX_Return should have children (its return value expression)
    return_node = tree[0]
    assert 'children' in return_node

    # 3. Both outputs are JSON serializable
    json.dumps(flat)  # should not raise
    json.dumps(tree)  # should not raise


# ===========================================================================
# Task 5: integration tests
# ===========================================================================

UASSET_DIR = pytest.importorskip("pathlib").Path(
    r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson"
)


def _find_first_uasset() -> str | None:
    """Find first BP_*.uasset file in sample directory."""
    candidates = list(UASSET_DIR.rglob("BP_*.uasset"))
    return str(candidates[0]) if candidates else None


def test_extract_bytecode_from_uasset():
    """End-to-end: extract bytecode from real .uasset file."""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    from uasset_read.kismet.bytecode_extractor import (
        extract_bytecode_bytes, parse_bytecode_stream, USTRUCT_TYPES,
    )
    from uasset_read.serializers.object_resources import resolve_class_name
    from uasset_read.archive import FArchive

    uasset_path = _find_first_uasset()
    if uasset_path is None:
        pytest.skip("No BP_*.uasset files found in FirstPerson samples")

    result = parse_uasset_with_linker(uasset_path)
    if result is None or result.summary is None:
        pytest.skip(f"Failed to parse {uasset_path}")

    archive = FArchive(uasset_path)
    try:
        summary = result.summary
        name_map = result.name_map
        export_map = result.export_map
        import_map = result.import_map

        # Find at least one UStruct export with bytecode
        found_bytecode = False
        for export in export_map:
            class_name = resolve_class_name(
                export.class_index, import_map, export_map
            )
            if class_name in USTRUCT_TYPES and export.script_serial_size > 10:
                bytecode = extract_bytecode_bytes(
                    archive, export, summary, name_map, import_map, export_map
                )
                if bytecode is not None and len(bytecode) > 0:
                    found_bytecode = True
                    assert isinstance(bytecode, bytes)
                    # Parse it to verify it's valid
                    exprs = parse_bytecode_stream(bytecode, name_map)
                    assert len(exprs) > 0
                    break
    finally:
        archive.close()

    if not found_bytecode:
        pytest.skip(f"No UStruct bytecode found in {uasset_path}")


def test_parse_bytecode_to_expressions():
    """End-to-end: parse bytecode to expression list."""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    from uasset_read.kismet.bytecode_extractor import (
        extract_bytecode_bytes, parse_bytecode_stream, USTRUCT_TYPES,
    )
    from uasset_read.serializers.object_resources import resolve_class_name
    from uasset_read.archive import FArchive

    uasset_path = _find_first_uasset()
    if uasset_path is None:
        pytest.skip("No BP_*.uasset files found")

    result = parse_uasset_with_linker(uasset_path)
    if result is None:
        pytest.skip(f"Failed to parse {uasset_path}")

    archive = FArchive(uasset_path)
    try:
        summary = result.summary
        name_map = result.name_map
        export_map = result.export_map
        import_map = result.import_map

        found_expressions = False
        for export in export_map:
            class_name = resolve_class_name(
                export.class_index, import_map, export_map
            )
            if class_name in USTRUCT_TYPES and export.script_serial_size > 10:
                bytecode = extract_bytecode_bytes(
                    archive, export, summary, name_map, import_map, export_map
                )
                if bytecode is not None and len(bytecode) > 0:
                    exprs = parse_bytecode_stream(bytecode, name_map)
                    if len(exprs) > 0:
                        found_expressions = True
                        # All expressions should have Token attribute
                        assert all(
                            hasattr(e, 'Token') for e in exprs
                        )
                        break
    finally:
        archive.close()

    if not found_expressions:
        pytest.skip(f"No parseable bytecode found in {uasset_path}")


def test_tolerant_mode_vs_strict_mode():
    """Compare tolerant vs strict mode on malformed bytecode."""
    from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream

    # Construct bytecode with known tokens only: EX_EndOfScript
    valid_bytecode = b'\x53'

    # 1. Strict mode: valid bytecode parses fine
    exprs = parse_bytecode_stream(valid_bytecode, [])
    assert len(exprs) == 1

    # 2. Malformed: unknown token in strict mode
    malformed = b'\xFF\x53'
    with pytest.raises(ParseError):
        parse_bytecode_stream(malformed, [], tolerant=False)

    # 3. Same malformed bytecode in tolerant mode: skips unknown, reads known
    exprs = parse_bytecode_stream(malformed, [], tolerant=True)
    assert len(exprs) == 1
    assert exprs[0].Token == EExprToken.EX_EndOfScript

    # 4. Tolerant mode with too many unknown tokens: should fail
    too_many_unknowns = bytes([0xFF] * 10)
    with pytest.raises(ParseError, match="Too many consecutive unknown tokens"):
        parse_bytecode_stream(too_many_unknowns, [], tolerant=True)
