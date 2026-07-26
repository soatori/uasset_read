"""Tests for batch output quality — errors visible in output files."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.core import parse_batch

_SAMPLE_DIR = Path(__file__).resolve().parent.parent / "samples"


class TestBatchOutputValidation:
    """Verify batch output files contain correct status and error information."""

    def test_batch_output_files_are_valid_json(self, tmp_path: Path):
        """Every output file from batch must be valid JSON."""
        out_dir = tmp_path / "output"
        result = parse_batch(str(_SAMPLE_DIR), output_dir=str(out_dir))

        assert result.total > 0, "No samples found"
        for output_path in result.success:
            p = Path(output_path)
            assert p.exists(), f"Missing output: {output_path}"
            data = json.loads(p.read_text(encoding="utf-8"))
            assert isinstance(data, dict), f"Not a JSON object: {output_path}"

    def test_batch_output_has_status_field(self, tmp_path: Path):
        """Every batch output JSON must have a top-level status field."""
        out_dir = tmp_path / "output"
        result = parse_batch(str(_SAMPLE_DIR), output_dir=str(out_dir))

        for output_path in result.success:
            data = json.loads(Path(output_path).read_text(encoding="utf-8"))
            assert "status" in data, f"Missing status in {output_path}"

    def test_batch_failure_list_is_nonempty_on_error(self, tmp_path: Path):
        """Batch result must raise ValueError for non-existent directory."""
        with pytest.raises(ValueError, match="Not a directory"):
            parse_batch(str(tmp_path / "nonexistent"), output_dir=str(tmp_path / "out"))

    def test_batch_output_contains_diagnostics(self, tmp_path: Path):
        """Batch output must contain diagnostics when present."""
        out_dir = tmp_path / "output"
        result = parse_batch(str(_SAMPLE_DIR), output_dir=str(out_dir))

        for output_path in result.success:
            data = json.loads(Path(output_path).read_text(encoding="utf-8"))
            if "diagnostics" in data:
                assert isinstance(data["diagnostics"], list), (
                    f"diagnostics is not a list in {output_path}"
                )
