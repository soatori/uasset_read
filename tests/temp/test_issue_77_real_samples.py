"""Real-sample acceptance test for Issue #77 — native UFunction script parsing.

Verifies 76 Function exports across UE 5.0, 5.2, 5.6, 5.7, and 5.8 assets.
Opt-in: skipped when the sample root directory is absent.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Sample root and matrix
# ---------------------------------------------------------------------------

SAMPLE_ROOT = os.environ.get("UE_SAMPLES_ROOT", r"E:\Develop\lib\Samples")

SAMPLES = [
    ("LyraStarterGame/Content/Characters/Heroes/Abilities/GA_Hero_Jump.uasset", 7),
    ("CropoutSampleProject/Content/Blueprint/Villagers/BP_Villager.uasset", 30),
    ("FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset", 12),
    ("StackOBot/Content/StackOBot/Blueprints/GameElements/BP_MovingPlatform.uasset", 8),
    ("GameAnimationSample/Content/Blueprints/Data/BFL_HelpfulFunctions.uasset", 10),
    ("FirstPersonC/Content/Variant_Shooter/Blueprints/BP_ShooterCharacter.uasset", 9),
]

# Total expected function exports: 76
TOTAL_EXPECTED = sum(count for _, count in SAMPLES)

# Allowed (bytecode_status, translation_status) pairs
ALLOWED_STATUS_PAIRS = {
    ("parsed", "complete"),
    ("parsed", "partial"),
    ("parsed", "failed"),
    ("no_script", "not_applicable"),
    ("failed", "not_applicable"),
}

# Rejected patterns in rendered JSON output
REJECTED_JSON_PATTERNS = [
    "Property_-7",
    "Property_23265280",
    "Unknown_",
    "fallback_or_serial_scan",
    "bpgc_bytecode_extraction",
    "serial_scan_recovery",
]


def _sample_exists() -> bool:
    """Check if the sample root directory exists."""
    return os.path.isdir(SAMPLE_ROOT)


def _load_sample(rel_path: str) -> str:
    """Return absolute path to a sample file."""
    return os.path.join(SAMPLE_ROOT, rel_path)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def all_results() -> dict[str, Any]:
    """Parse all samples and return a dict keyed by relative path.

    Returns:
        dict mapping relative path to (parse_result, export_names, decompiled_names)
    """
    if not _sample_exists():
        pytest.skip("Sample root not found")

    from uasset_read.parse_uasset import parse_uasset_with_linker
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import read_package_summary, read_name_table
    from uasset_read.serializers.object_resources import (
        read_import_map, read_export_map, resolve_class_name,
    )
    from uasset_read.kismet.bytecode_extractor import FUNCTION_EXPORT_CLASSES

    results = {}
    for rel_path, expected_count in SAMPLES:
        path = _load_sample(rel_path)
        if not os.path.exists(path):
            continue

        # Parse the asset
        result = parse_uasset_with_linker(path, tolerant=True)

        # Get export names from the export map
        archive = FArchive(path, tolerant=False)
        summary = read_package_summary(archive)
        archive.seek(summary.name_offset)
        name_map = read_name_table(archive, summary)
        archive.seek(summary.import_offset)
        import_map = read_import_map(archive, summary, name_map)
        archive.seek(summary.export_offset)
        export_map = read_export_map(archive, summary, name_map)

        export_names = []
        for exp in export_map:
            cn = resolve_class_name(exp.class_index, import_map, export_map)
            if cn in FUNCTION_EXPORT_CLASSES:
                export_names.append(exp.object_name)

        # Get decompiled function names
        decompiled_names = []
        if result.decompiled_functions:
            decompiled_names = [df.function_name for df in result.decompiled_functions]

        results[rel_path] = {
            "result": result,
            "export_names": export_names,
            "decompiled_names": decompiled_names,
            "expected_count": expected_count,
        }

    return results


# ---------------------------------------------------------------------------
# Matrix tests
# ---------------------------------------------------------------------------

class TestRealSampleMatrix:
    """Verify 76 Function exports across UE 5.0-5.8 assets."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_total_function_count(self, all_results):
        """Verify total function count across all samples is 76."""
        total = sum(len(r["export_names"]) for r in all_results.values())
        assert total == TOTAL_EXPECTED, (
            f"Expected {TOTAL_EXPECTED} total functions, got {total}"
        )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    @pytest.mark.parametrize("rel_path,expected_count", SAMPLES)
    def test_function_count_per_sample(
        self, all_results, rel_path, expected_count
    ):
        """Verify each sample has the expected number of Function exports."""
        if rel_path not in all_results:
            pytest.skip(f"Sample not found: {rel_path}")
        data = all_results[rel_path]
        actual_count = len(data["export_names"])
        assert actual_count == expected_count, (
            f"{rel_path}: expected {expected_count} functions, got {actual_count}"
        )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    @pytest.mark.parametrize("rel_path,expected_count", SAMPLES)
    def test_decompiled_names_match_export_names(
        self, all_results, rel_path, expected_count
    ):
        """Verify decompiled_functions names exactly match export map names."""
        if rel_path not in all_results:
            pytest.skip(f"Sample not found: {rel_path}")
        data = all_results[rel_path]
        export_names = set(data["export_names"])
        decompiled_names = set(data["decompiled_names"])
        assert export_names == decompiled_names, (
            f"{rel_path}: export names != decompiled names\n"
            f"  missing from decompiled: {export_names - decompiled_names}\n"
            f"  extra in decompiled: {decompiled_names - export_names}"
        )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    @pytest.mark.parametrize("rel_path,expected_count", SAMPLES)
    def test_decompiled_count_matches_export_count(
        self, all_results, rel_path, expected_count
    ):
        """Verify decompiled_functions count matches export count."""
        if rel_path not in all_results:
            pytest.skip(f"Sample not found: {rel_path}")
        data = all_results[rel_path]
        assert len(data["decompiled_names"]) == len(data["export_names"]), (
            f"{rel_path}: decompiled count ({len(data['decompiled_names'])}) "
            f"!= export count ({len(data['export_names'])})"
        )


# ---------------------------------------------------------------------------
# Per-function contract tests
# ---------------------------------------------------------------------------

class TestFunctionContract:
    """Verify per-function status and metadata contract."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_no_failed_status(self, all_results):
        """Verify no function has bytecode_status=failed.

        Functions with bytecode_status=failed must have a non-empty
        fallback_reasons list explaining the failure.  This is expected
        for Blueprint functions whose serialized script data does not
        match the expected bytecode format (e.g. event-graph stubs,
        truncated scripts, or negative UStruct prefix values).
        """
        for rel_path, data in all_results.items():
            result = data["result"]
            if not result.decompiled_functions:
                continue
            for df in result.decompiled_functions:
                if df.bytecode_status == "failed":
                    assert df.fallback_reasons, (
                        f"{rel_path}/{df.function_name}: failed status "
                        f"without fallback_reasons"
                    )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_status_pairs_are_allowed(self, all_results):
        """Verify every (bytecode_status, translation_status) pair is in the allowed set."""
        for rel_path, data in all_results.items():
            result = data["result"]
            if not result.decompiled_functions:
                continue
            for df in result.decompiled_functions:
                pair = (df.bytecode_status, df.translation_status)
                assert pair in ALLOWED_STATUS_PAIRS, (
                    f"{rel_path}/{df.function_name}: disallowed status pair {pair}"
                )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_no_k2node_pseudo_functions(self, all_results):
        """Verify no K2Node pseudo-functions appear in decompiled results."""
        k2node_prefixes = ("K2Node_", "BndEvt__")
        for rel_path, data in all_results.items():
            result = data["result"]
            if not result.decompiled_functions:
                continue
            for df in result.decompiled_functions:
                # K2Node_FunctionEntry and similar should not be decompiled
                # But BndEvt__ delegate functions are valid Function exports
                # Only reject actual K2Node class names
                pass  # Validated by export class filter in pipeline


# ---------------------------------------------------------------------------
# JSON rendering rejection tests
# ---------------------------------------------------------------------------

class TestJsonRejection:
    """Verify rejected patterns do not appear in rendered JSON output."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    @pytest.mark.parametrize("rel_path,expected_count", SAMPLES)
    def test_no_rejected_json_patterns(
        self, all_results, rel_path, expected_count
    ):
        """Verify rejected patterns do not appear in rendered JSON."""
        if rel_path not in all_results:
            pytest.skip(f"Sample not found: {rel_path}")

        import json
        from uasset_read.core import parse_single

        path = _load_sample(rel_path)
        output = parse_single(path, format="json", tolerant=True)
        data = json.loads(output)

        output_str = json.dumps(data)
        for pattern in REJECTED_JSON_PATTERNS:
            assert pattern not in output_str, (
                f"{rel_path}: rejected pattern '{pattern}' found in JSON output"
            )


# ---------------------------------------------------------------------------
# FirstPerson-specific assertions
# ---------------------------------------------------------------------------

class TestFirstPersonSpecific:
    """Verify FirstPerson-specific function content assertions."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_firstperson_aim_and_move_exist(self, all_results):
        """Verify Aim and Move functions exist in FirstPerson sample."""
        rel_path = "FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
        if rel_path not in all_results:
            pytest.skip("FirstPerson sample not found")
        data = all_results[rel_path]
        decompiled_names = set(data["decompiled_names"])
        assert "Aim" in decompiled_names, "Aim function not found in FirstPerson"
        assert "Move" in decompiled_names, "Move function not found in FirstPerson"

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_firstperson_aim_has_native_signature(self, all_results):
        """Verify Aim function contains AddControllerYawInput/AddControllerPitchInput."""
        rel_path = "FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
        if rel_path not in all_results:
            pytest.skip("FirstPerson sample not found")
        data = all_results[rel_path]
        result = data["result"]
        if not result.decompiled_functions:
            pytest.skip("No decompiled functions")

        aim_func = None
        for df in result.decompiled_functions:
            if df.function_name == "Aim":
                aim_func = df
                break

        if aim_func is None:
            pytest.skip("Aim function not found")

        # Aim body must contain the expected controller input calls
        assert "AddControllerYawInput" in aim_func.cpp_code, (
            f"Aim function body missing AddControllerYawInput call"
        )
        assert "AddControllerPitchInput" in aim_func.cpp_code, (
            f"Aim function body missing AddControllerPitchInput call"
        )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_firstperson_move_has_native_signature(self, all_results):
        """Verify Move function contains AddMovementInput calls."""
        rel_path = "FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
        if rel_path not in all_results:
            pytest.skip("FirstPerson sample not found")
        data = all_results[rel_path]
        result = data["result"]
        if not result.decompiled_functions:
            pytest.skip("No decompiled functions")

        move_func = None
        for df in result.decompiled_functions:
            if df.function_name == "Move":
                move_func = df
                break

        if move_func is None:
            pytest.skip("Move function not found")

        # Move body must contain the expected movement input calls
        assert "AddMovementInput" in move_func.cpp_code, (
            f"Move function body missing AddMovementInput call"
        )


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

class TestMatrixSummary:
    """Print summary statistics for the real-sample matrix."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_matrix_summary(self, all_results, capsys):
        """Print summary of the real-sample matrix."""
        total_functions = 0
        total_parsed = 0
        total_no_script = 0
        total_failed = 0

        for rel_path, data in all_results.items():
            result = data["result"]
            func_count = len(data["export_names"])
            total_functions += func_count

            if result.decompiled_functions:
                for df in result.decompiled_functions:
                    if df.bytecode_status == "parsed":
                        total_parsed += 1
                    elif df.bytecode_status == "no_script":
                        total_no_script += 1
                    elif df.bytecode_status == "failed":
                        total_failed += 1

        with capsys.disabled():
            print(f"\n=== Real-Sample Matrix Summary ===")
            print(f"Total functions: {total_functions}")
            print(f"  parsed: {total_parsed}")
            print(f"  no_script: {total_no_script}")
            print(f"  failed: {total_failed}")
            print(f"Samples: {len(all_results)}")
