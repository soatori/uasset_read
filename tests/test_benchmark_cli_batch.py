"""Benchmark the public CLI and batch export contracts."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from uasset_read import parse_batch


def _run_cli(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo_root / "run.py"), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@pytest.mark.benchmark
def test_cli_and_batch_public_contract(
    blueprint_sample,
    samples_dir,
    measure,
    tmp_path,
):
    repo_root = Path(__file__).resolve().parents[1]
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    batch_samples = (
        "FirstPerson_BP_FirstPersonGameMode.uasset",
        "Lyra_Enum_PanelType.uasset",
    )
    for name in batch_samples:
        source = samples_dir / name
        assert source.is_file(), f"Batch benchmark sample is missing: {source}"
        shutil.copy2(source, input_dir / name)

    with measure("cli_batch"):
        formats = _run_cli(repo_root, "--list-formats")
        single = _run_cli(
            repo_root,
            str(blueprint_sample),
            "--json",
            "--full-parse",
            "--log-level",
            "off",
        )
        batch = parse_batch(
            str(input_dir),
            format="json",
            output_dir=str(output_dir),
            tolerant=True,
            isolate_assets=False,
            log_enabled=False,
        )

    assert formats.returncode == 0, formats.stderr
    assert "--json" in formats.stdout
    assert "--markdown" in formats.stdout

    assert single.returncode == 0, single.stderr
    single_payload = json.loads(single.stdout)
    assert single_payload["status"].get("status") in {"success", "partial"}

    assert batch.total == len(batch_samples)
    assert len(batch.success) == len(batch_samples)
    assert not batch.failed
    assert not batch.skipped
    outputs = sorted(output_dir.glob("*.json"))
    assert len(outputs) == len(batch_samples)
    for output in outputs:
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["status"].get("status") in {"success", "partial"}
