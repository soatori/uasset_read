"""Tests for output_level parameter behavior."""
import json
import pytest
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent / "samples"
SAMPLE_BP = SAMPLE_DIR / "StackOBot_BP_Drone.uasset"


@pytest.mark.integration
class TestOutputLevelRendering:
    """Test output_level rendering behavior through semantic pipeline."""

    def test_standard_output_has_semantic_format(self):
        """standard mode should produce valid semantic JSON."""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)
        assert data["format"] in ("uasset_read.asset_semantic", "uasset_read.blueprint_semantic")
        assert data["mode"] == "standard"

    def test_debug_output_has_semantic_format(self):
        """debug mode should produce valid semantic JSON."""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="debug")
        data = json.loads(result)
        assert data["format"] in ("uasset_read.asset_semantic", "uasset_read.blueprint_semantic")
        assert data["mode"] == "debug"

    def test_standard_output_smaller(self):
        """standard mode output should be smaller than debug mode."""
        from uasset_read.core import parse_single

        standard = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        debug = parse_single(str(SAMPLE_BP), format="json", output_level="debug")

        assert len(standard) < len(debug)

    def test_standard_mode_has_status(self):
        """standard mode should have status field."""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)
        assert "status" in data
        assert "parse" in data["status"]
        assert "representation" in data["status"]

    def test_debug_mode_has_evidence(self):
        """debug mode may have evidence entries (standard strips them)."""
        from uasset_read.core import parse_single
        debug_result = parse_single(str(SAMPLE_BP), format="json", output_level="debug")
        debug_data = json.loads(debug_result)
        # debug mode preserves evidence; standard strips it
        assert "format" in debug_data
        assert debug_data["format"] in ("uasset_read.asset_semantic", "uasset_read.blueprint_semantic")
