"""Regression tests for semantic_json against real .uasset samples.

These tests require sample files at E:\\Develop\\lib\\Samples.
They are skipped automatically when samples are not available.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SAMPLES_DIR = Path(r"E:\Develop\lib\Samples")

# Asset files and their expected kinds
SAMPLE_ASSETS: list[tuple[str, str]] = [
    # (relative_path, expected_kind)
    # Add real sample paths here as they become available
]


def _samples_available() -> bool:
    """Check if sample directory exists and has .uasset files."""
    return SAMPLES_DIR.is_dir() and any(SAMPLES_DIR.rglob("*.uasset"))


pytestmark = pytest.mark.skipif(
    not _samples_available(),
    reason="Sample .uasset files not available at E:\\Develop\\lib\\Samples",
)


@pytest.fixture()
def sample_dir() -> Path:
    """Return the samples directory."""
    return SAMPLES_DIR


def test_semantic_json_parse_no_crash(sample_dir: Path) -> None:
    """Parse all available samples without crashing."""
    from uasset_read.core import parse_single

    uasset_files = list(sample_dir.rglob("*.uasset"))
    assert len(uasset_files) > 0, "No .uasset files found in samples"

    failures: list[str] = []
    for asset_path in uasset_files[:10]:  # Limit to first 10 for speed
        try:
            result_str = parse_single(
                str(asset_path),
                format="semantic_json",
            )
            # parse_single returns a JSON string; parse it to validate
            data = json.loads(result_str)
            status = data.get("status", {}).get("status", "ok")
            if status == "failed":
                failures.append(f"{asset_path.name}: parse reported 'failed' status")
        except Exception as e:
            failures.append(f"{asset_path.name}: {type(e).__name__}: {e}")

    if failures:
        pytest.fail(
            f"Failed to parse {len(failures)} assets:\n" + "\n".join(failures)
        )


def test_semantic_json_output_structure(sample_dir: Path) -> None:
    """Verify output structure matches schema for all parsed samples."""
    from uasset_read.core import parse_single

    uasset_files = list(sample_dir.rglob("*.uasset"))
    assert len(uasset_files) > 0

    for asset_path in uasset_files[:5]:  # Limit for speed
        result_str = parse_single(
            str(asset_path),
            format="semantic_json",
        )
        data = json.loads(result_str)

        # Must have required top-level keys
        for key in ("format", "format_version", "mode", "asset",
                     "references", "content", "coverage", "diagnostics"):
            assert key in data, f"Missing key '{key}' in {asset_path.name}"

        # Format constant
        assert data["format"] == "uasset_read.asset_semantic"
        assert data["format_version"] == "1.0.0"

        # Asset meta
        asset = data["asset"]
        assert asset["kind"] in ("graph", "structured", "resource", "opaque")
        assert len(asset["class_name"]) > 0
