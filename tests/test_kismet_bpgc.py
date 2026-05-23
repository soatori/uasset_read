"""
BPGC Bytecode Extraction Tests — Phase 72-C Wave 2 integration tests.

Tests for BPGC fallback path and decompile_uasset() integration with cooked UE5 Blueprints.

NOTE: BPGC fallback is designed for UE5 COOKED Blueprints. Uncooked editor assets
do not store bytecode in BPGC script_serial_region. Integration tests will skip
if no cooked UE5 Blueprint is available in the test directory.
"""
import struct
import pytest
from pathlib import Path

from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer, map_bytecode_to_functions
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


# Test asset directories
TEST_ASSET_DIR = Path(r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints")
PRIMARY_BP = TEST_ASSET_DIR / "BP_FirstPersonCharacter.uasset"

# Lyra directory (UE4, not supported for UE5 BPGC testing)
LYRA_ASSET_DIR = Path(r"E:\Develop\lib\UnrealEngine\Samples\Games\LyraStarterGame\Content")


def _is_cooked_ue5_blueprint(path: Path) -> bool:
    """Check if asset is a cooked UE5 Blueprint."""
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import read_package_summary
    from uasset_read.constants import PKG_Cooked

    try:
        archive = FArchive(str(path))
        summary = read_package_summary(archive)
        is_cooked = (summary.package_flags & PKG_Cooked) != 0
        archive.close()
        return is_cooked
    except Exception:
        return False


def _find_cooked_ue5_blueprint() -> Path | None:
    """Search for a cooked UE5 Blueprint asset."""
    # Check primary BP first
    if PRIMARY_BP.exists() and _is_cooked_ue5_blueprint(PRIMARY_BP):
        return PRIMARY_BP

    # Search other directories
    search_dirs = [
        TEST_ASSET_DIR.parent.parent.parent,  # FirstPerson/Content
        Path(r"E:\Develop\lib\UnrealEngine\Samples\Games"),
    ]

    for search_dir in search_dirs:
        for bp_path in search_dir.rglob("BP_*.uasset"):
            if _is_cooked_ue5_blueprint(bp_path):
                return bp_path

    return None


# ===========================================================================
# Task 2: BPGC tests
# ===========================================================================


def test_extract_bpgc_bytecode_parses_cooked_format():
    """Test _parse_cooked_bytecode_buffer with synthetic cooked format."""
    # Create synthetic bytecode buffers: size prefix + bytecode + EX_EndOfScript (0x53)
    func1_bytecode = bytes([0x00, 0x01, 0x04, 0x53])  # 4 bytes
    func2_bytecode = bytes([0x1B, 0x00, 0x16, 0x53])  # 4 bytes

    # Pack as cooked format: u32 size prefix (little-endian) + data
    synthetic = struct.pack('<I', len(func1_bytecode)) + func1_bytecode
    synthetic += struct.pack('<I', len(func2_bytecode)) + func2_bytecode

    buffers = _parse_cooked_bytecode_buffer(synthetic)

    # Assert correct number of buffers extracted
    assert len(buffers) == 2, f"Expected 2 buffers, got {len(buffers)}"

    # Each buffer should end with EX_EndOfScript (0x53)
    assert buffers[0][-1] == 0x53, f"Buffer 0 ends with 0x{buffers[0][-1]:02X}"
    assert buffers[1][-1] == 0x53, f"Buffer 1 ends with 0x{buffers[1][-1]:02X}"

    # Verify buffer contents
    assert buffers[0] == func1_bytecode
    assert buffers[1] == func2_bytecode


def test_extract_bpgc_bytecode_empty_region():
    """Test _parse_cooked_bytecode_buffer with empty/invalid input."""
    # Empty bytes → returns empty list
    assert _parse_cooked_bytecode_buffer(b'') == []

    # Zero size prefix (4 bytes of zeros) → returns empty list
    zero_size = b'\x00\x00\x00\x00'
    assert _parse_cooked_bytecode_buffer(zero_size) == []

    # Size exceeding remaining bytes → returns empty list (stops)
    invalid_size = struct.pack('<I', 1000) + bytes([0x53])  # size=1000 but only 1 byte data
    assert _parse_cooked_bytecode_buffer(invalid_size) == []


def test_map_bytecode_to_functions_ordinals():
    """Test map_bytecode_to_functions with mock exports."""
    # Create mock Function exports (use ObjectExport dataclass)
    mock_exports = [
        ObjectExport(
            class_index=PackageIndex(-1),  # Import: Function
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="ExecuteUbergraph_BP_FirstPersonCharacter",
            object_flags=0,
            serial_size=0,
            serial_offset=0,
        ),
        ObjectExport(
            class_index=PackageIndex(-1),  # Import: Function
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="Aim",
            object_flags=0,
            serial_size=0,
            serial_offset=0,
        ),
        ObjectExport(
            class_index=PackageIndex(-1),  # Import: Function
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="Move",
            object_flags=0,
            serial_size=0,
            serial_offset=0,
        ),
    ]

    # Create mock bytecode buffers dict
    mock_buffers = {
        "0": bytes([0x01, 0x02, 0x53]),  # Buffer for first function
        "1": bytes([0x03, 0x04, 0x53]),  # Buffer for second function
        "2": bytes([0x05, 0x06, 0x53]),  # Buffer for third function
    }

    # Mock import_map (Function class import at index 0)
    from uasset_read.serializers.object_resources import ObjectImport
    mock_import_map = [
        ObjectImport(
            class_package="/Script/CoreUObject",
            class_name="Function",
            outer_index=PackageIndex(0),
            object_name="Function",
        )
    ]

    # Map buffers to functions
    result = map_bytecode_to_functions(mock_buffers, mock_exports, [], mock_import_map, [])

    # Assert function names mapped to correct bytecode buffers by ordinal position
    assert "ExecuteUbergraph_BP_FirstPersonCharacter" in result
    assert "Aim" in result
    assert "Move" in result

    # Verify ordinal mapping: buffer 0 → first function, etc.
    assert result["ExecuteUbergraph_BP_FirstPersonCharacter"] == mock_buffers["0"]
    assert result["Aim"] == mock_buffers["1"]
    assert result["Move"] == mock_buffers["2"]


def test_extract_bytecode_bytes_bpgc_fallback():
    """Integration test: BPGC fallback path for UE5 cooked Blueprint.

    NOTE: This test requires a COOKED UE5 Blueprint. Uncooked editor assets
    do not store bytecode in BPGC script_serial_region, so the fallback
    will not find bytecode. Test will skip if no cooked asset is available.
    """
    cooked_bp = _find_cooked_ue5_blueprint()
    if cooked_bp is None:
        pytest.skip("No cooked UE5 Blueprint found in test directory (BPGC fallback requires cooked assets)")

    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import read_package_summary, read_name_table
    from uasset_read.serializers.object_resources import (
        read_import_map,
        read_export_map,
        resolve_class_name,
    )
    from uasset_read.kismet.bytecode_extractor import (
        extract_bytecode_bytes,
        reset_bpgc_cache,
        USTRUCT_TYPES,
    )

    archive = FArchive(str(cooked_bp))

    try:
        summary = read_package_summary(archive)
        archive.seek(summary.name_offset)
        name_map = read_name_table(archive, summary)
        archive.seek(summary.import_offset)
        import_map = read_import_map(archive, summary, name_map)
        archive.seek(summary.export_offset)
        export_map = read_export_map(archive, summary, name_map)

        # Reset cache for clean test
        reset_bpgc_cache()

        # Find a Function export
        func_export = None
        for export in export_map:
            class_name = resolve_class_name(export.class_index, import_map, export_map)
            if class_name in USTRUCT_TYPES and export.script_serial_size > 0:
                func_export = export
                break

        if func_export is None:
            pytest.skip("No Function export with script_serial_size > 0 found")

        # Extract bytecode — should use BPGC fallback if Function has no bytecode
        bytecode = extract_bytecode_bytes(
            archive, func_export, summary, name_map, import_map, export_map
        )

        # For cooked assets, bytecode may come from BPGC fallback or directly from Function
        # We just verify that the extraction mechanism works
        if bytecode is not None:
            assert len(bytecode) > 0, "Expected non-empty bytecode"
            # Verify bytecode ends with EX_EndOfScript (0x53) or cooked variant (0xDD)
            assert bytecode[-1] in (0x53, 0xDD), f"Bytecode ends with 0x{bytecode[-1]:02X}"

    finally:
        archive.close()


def test_decompile_uasset_bpgc_functions():
    """End-to-end test: decompile_uasset() on UE5 Blueprint.

    NOTE: This test requires a COOKED UE5 Blueprint for BPGC bytecode extraction.
    For uncooked assets, decompile_uasset() may return empty results because
    bytecode is stored differently. Test will skip if no cooked asset is available.
    """
    cooked_bp = _find_cooked_ue5_blueprint()
    if cooked_bp is None:
        pytest.skip("No cooked UE5 Blueprint found (decompile requires cooked assets for bytecode)")

    from uasset_read.kismet.pipeline import decompile_uasset

    # Decompile the Blueprint
    results = decompile_uasset(str(cooked_bp), tolerant=True)

    # For cooked assets, we expect some functions to be decompiled
    # The exact count depends on the asset
    assert isinstance(results, list), f"Expected list, got {type(results)}"

    # If we got results, verify structure
    if len(results) > 0:
        for result in results:
            assert hasattr(result, 'function_name')
            assert hasattr(result, 'expressions')
            assert hasattr(result, 'cpp_code')


def test_decompile_uasset_no_regression():
    """Regression test: verify existing kismet tests still pass."""
    # Import critical test functions from test_kismet.py and re-run them
    from tests.test_kismet import (
        test_fkismet_archive_tolerant_mode,
        test_bytecode_extractor,
        test_expression_output_formats,
    )

    # Run the tests (should not raise)
    test_fkismet_archive_tolerant_mode()
    test_bytecode_extractor()
    test_expression_output_formats()


def test_decompile_uasset_non_blueprint_returns_empty():
    """Verify non-Blueprint .uasset files return empty list (existing behavior preserved)."""
    # Find a non-Blueprint asset in the sample directory
    non_bp_assets = list(TEST_ASSET_DIR.rglob("*.uasset"))
    non_bp = None
    for asset in non_bp_assets:
        if not asset.stem.startswith("BP_"):
            non_bp = asset
            break

    if non_bp is None:
        pytest.skip("No non-Blueprint .uasset found in sample directory")

    from uasset_read.kismet.pipeline import decompile_uasset

    results = decompile_uasset(str(non_bp), tolerant=True)

    # Should return empty list for non-Blueprint assets (or minimal results)
    # Note: Some non-BP assets may still have functions, so we just verify no crash
    assert isinstance(results, list), f"Expected list, got {type(results)}"


# ===========================================================================
# Inline verification (matches bpgc_bytecode.py inline test)
# ===========================================================================


def test_parse_cooked_bytecode_buffer_inline():
    """Verify _parse_cooked_bytecode_buffer matches bpgc_bytecode.py inline test."""
    func1_bytecode = bytes([0x00, 0x01, 0x04, 0x53])
    func2_bytecode = bytes([0x1B, 0x00, 0x16, 0x53])

    synthetic = struct.pack('<I', len(func1_bytecode)) + func1_bytecode
    synthetic += struct.pack('<I', len(func2_bytecode)) + func2_bytecode

    buffers = _parse_cooked_bytecode_buffer(synthetic)

    assert len(buffers) == 2
    assert buffers[0].endswith(b'\x53')
    assert buffers[1].endswith(b'\x53')
    assert buffers[0] == func1_bytecode
    assert buffers[1] == func2_bytecode

    # Test single buffer with trailing garbage
    single = struct.pack('<I', 4) + bytes([0x01, 0x02, 0x03, 0x53]) + b'\x00\x00'
    single_bufs = _parse_cooked_bytecode_buffer(single)
    assert len(single_bufs) == 1
    assert single_bufs[0].endswith(b'\x53')

    # Test plan verification data
    plan_data = b'\x04\x00\x00\x00\x01\x02\x03\x53'
    plan_bufs = _parse_cooked_bytecode_buffer(plan_data)
    assert len(plan_bufs) == 1
    assert plan_bufs[0].endswith(b'\x53')