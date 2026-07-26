"""Regression tests for #439: batch parse must produce output for all inputs."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

_SAMPLE_DIR = Path(__file__).resolve().parent / "samples"


class TestBatchParallelLifecycle:
    """#439: batch parse must produce output for all inputs."""

    def test_all_samples_produce_output(self, tmp_path: Path):
        """Every input in a batch must produce a result with output."""
        from uasset_read.core import parse_batch

        out_dir = tmp_path / "output"
        result = parse_batch(
            str(_SAMPLE_DIR),
            output_dir=str(out_dir),
        )
        assert result.total == len(list(_SAMPLE_DIR.glob("*.uasset")))
        assert len(result.failed) == 0, (
            f"Batch produced {len(result.failed)} failures: "
            + "; ".join(f"{f[0]}: {f[1][:80]}" for f in result.failed[:5])
        )

    def test_all_outputs_exist_on_disk(self, tmp_path: Path):
        """Every success path must correspond to a real file on disk."""
        from uasset_read.core import parse_batch

        out_dir = tmp_path / "output"
        result = parse_batch(
            str(_SAMPLE_DIR),
            output_dir=str(out_dir),
        )
        for output_path in result.success:
            assert Path(output_path).is_file(), f"Missing output file: {output_path}"

    def test_isolated_batch_all_samples_produce_output(self, tmp_path: Path):
        """Subprocess-isolated batch must produce output for all inputs."""
        from uasset_read.core import parse_batch

        out_dir = tmp_path / "output"
        result = parse_batch(
            str(_SAMPLE_DIR),
            output_dir=str(out_dir),
            isolate_assets=True,
        )
        assert result.total == len(list(_SAMPLE_DIR.glob("*.uasset")))
        assert len(result.failed) == 0, (
            f"Isolated batch produced {len(result.failed)} failures: "
            + "; ".join(f"{f[0]}: {f[1][:80]}" for f in result.failed[:5])
        )
