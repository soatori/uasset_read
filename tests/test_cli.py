"""CLI regression tests — single package, normal by default, ``--debug`` only."""

import json
import sys

import pytest

from tests.fixtures import sample_path
from uasset_read import cli


# Historical retired surfaces: v2 logging/legacy flags and the v3 public-output
# view/depth/limit/max_bytes/batch flags. They must keep failing loudly, so the
# literals stay here as rejection fixtures (not as supported CLI surfaces).
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
        "--depth",
        "--limit",
        "--max-bytes",
        "--batch",
        "--batch-format",
        "--list-package-files",
    ],
)
def test_unknown_flags_are_rejected(monkeypatch, flag: str) -> None:
    """Retired and unknown flags fall through to argparse; main() maps them to exit 3."""
    monkeypatch.setattr(sys, "argv", ["uasset_read", flag])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 3


def _run_cli(monkeypatch, *argv) -> int:
    monkeypatch.setattr(sys, "argv", ["uasset_read", *map(str, argv)])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    return excinfo.value.code


def test_cli_defaults_to_normal_mode(monkeypatch, capsys, tmp_path) -> None:
    sample = sample_path("StackOBot_BP_Drone.uasset")
    code = _run_cli(monkeypatch, str(sample))
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "uasset_read.package"
    assert payload["format_version"] == "4.0"
    assert payload["mode"] == "normal"
    assert "debug" not in payload

    out = tmp_path / "normal.json"
    code = _run_cli(monkeypatch, str(sample), "-o", str(out))
    assert code == 0
    file_payload = json.loads(out.read_text(encoding="utf-8"))
    assert file_payload["mode"] == "normal"
    assert file_payload == payload


def test_cli_debug_flag_emits_debug_mode(monkeypatch, capsys, tmp_path) -> None:
    sample = sample_path("StackOBot_BP_Drone.uasset")
    code = _run_cli(monkeypatch, str(sample), "--debug")
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "debug"
    assert set(payload["debug"]) == {
        "object_regions",
        "property_evidence",
        "semantic_source_ranges",
        "payload_sources",
        "sidecar_sources",
        "diagnostic_details",
        "byte_accounting",
    }

    out = tmp_path / "debug.json"
    code = _run_cli(monkeypatch, str(sample), "--debug", "-o", str(out))
    assert code == 0
    file_payload = json.loads(out.read_text(encoding="utf-8"))
    assert file_payload == payload


def test_cli_stdout_and_output_file_agree_per_mode(monkeypatch, capsys, tmp_path) -> None:
    sample = sample_path("StackOBot_BP_Drone.uasset")
    for extra in ([], ["--debug"]):
        code = _run_cli(monkeypatch, str(sample), *extra)
        assert code == 0
        stdout_payload = json.loads(capsys.readouterr().out)
        out = tmp_path / f"out-{len(extra)}.json"
        code = _run_cli(monkeypatch, str(sample), *extra, "-o", str(out))
        assert code == 0
        file_payload = json.loads(out.read_text(encoding="utf-8"))
        assert stdout_payload == file_payload


def test_cli_rejects_retired_flag_combinations(monkeypatch) -> None:
    sample = sample_path("StackOBot_BP_Drone.uasset")
    for flag, value in (
        ("--depth", "decode"),
        ("--limit", "2"),
        ("--max-bytes", "100"),
        ("--batch-format", "json"),
    ):
        code = _run_cli(monkeypatch, str(sample), flag, value)
        assert code == cli.EXIT_ARGUMENT_ERROR
    code = _run_cli(monkeypatch, str(sample), "--batch")
    assert code == cli.EXIT_ARGUMENT_ERROR
    code = _run_cli(monkeypatch, str(sample), "--list-package-files")
    assert code == cli.EXIT_ARGUMENT_ERROR


def test_cli_missing_file_is_file_not_found(monkeypatch, tmp_path) -> None:
    code = _run_cli(monkeypatch, str(tmp_path / "absent.uasset"))
    assert code == cli.EXIT_FILE_NOT_FOUND
