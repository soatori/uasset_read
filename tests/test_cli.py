"""CLI regression tests."""

import json
import sys
from pathlib import Path

import pytest

from tests.fixtures import sample_path
from uasset_read import cli


@pytest.mark.parametrize(
    "flag",
    [
        "--log-level",
        "--log-cleanup",
        "--no-log-cleanup",
        "--log-max-bytes",
        "--log-backup-count",
        "--log-format",
        "--include-parent-assets",
        "--asset-root",
        "--clean-logs",
        "--log-dir",
        "--log-keep-latest",
        "--log-max-total-mb",
        "--legacy-json",
        "--markdown",
        "--list-formats",
        "--diff",
    ],
)
def test_unknown_flags_are_rejected(monkeypatch, flag: str) -> None:
    """Removed flags fall through to argparse; main() maps unknown flags to exit 3."""
    monkeypatch.setattr(sys, "argv", ["uasset_read", flag])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 3


def _run_cli(monkeypatch, *argv) -> int:
    monkeypatch.setattr(sys, "argv", ["uasset_read", *map(str, argv)])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    return excinfo.value.code


def test_cli_output_file_writes_canonical_v3_document(monkeypatch, tmp_path) -> None:
    """`-o FILE` materializes one complete format_version 3.0 document."""
    sample = sample_path("StackOBot_BP_Drone.uasset")
    out = tmp_path / "canonical.json"
    code = _run_cli(monkeypatch, str(sample), "-o", str(out), "--depth", "decode")
    assert code == 0
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format"] == "uasset_read.package"
    assert payload["format_version"] == "3.0"
    assert "objects" in payload
    assert "projections" in payload
    assert all(item.get("embedded") for item in payload["projections"])
    # Canonical writer never paginates.
    assert "next_offset" not in payload
    assert "truncation" not in payload


def test_cli_rejects_limit_with_canonical_output(monkeypatch, tmp_path) -> None:
    """Canonical `-o` output cannot be combined with `--limit` (usage error)."""
    sample = sample_path("StackOBot_BP_Drone.uasset")
    out = tmp_path / "should_not_exist.json"
    code = _run_cli(monkeypatch, str(sample), "-o", str(out), "--limit", "2")
    assert code == cli.EXIT_ARGUMENT_ERROR
    assert not out.exists()


def test_cli_batch_results_are_complete_v3_documents(monkeypatch, tmp_path) -> None:
    """Batch envelope stays 1.0; each results[] entry is a full v3 canonical doc."""
    sample = sample_path("StackOBot_BP_Drone.uasset")
    batch_dir = tmp_path / "batch_in"
    batch_dir.mkdir()
    (batch_dir / sample.name).write_bytes(sample.read_bytes())
    out = tmp_path / "batch.json"
    code = _run_cli(
        monkeypatch,
        "--batch",
        str(batch_dir),
        "--batch-format",
        "json",
        "-o",
        str(out),
        "--depth",
        "package",
    )
    assert code == 0
    envelope = json.loads(out.read_text(encoding="utf-8"))
    assert envelope["format"] == "uasset_read.batch"
    assert envelope["format_version"] == "1.0"
    assert envelope["results"]
    succeeded = [item for item in envelope["results"] if not item.get("_error")]
    assert succeeded
    for item in succeeded:
        assert item["format"] == "uasset_read.package"
        assert item["format_version"] == "3.0"
        assert "objects" in item
        assert "projections" in item


def test_cli_rejects_limit_with_batch(monkeypatch, tmp_path) -> None:
    """Batch entries are complete canonical documents, so --limit is a usage error."""
    sample = sample_path("StackOBot_BP_Drone.uasset")
    batch_dir = tmp_path / "batch_in"
    batch_dir.mkdir()
    (batch_dir / sample.name).write_bytes(sample.read_bytes())
    code = _run_cli(monkeypatch, "--batch", str(batch_dir), "--limit", "2")
    assert code == cli.EXIT_ARGUMENT_ERROR
