from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.uasset_test as tool


pytestmark = pytest.mark.unit


def make_args(**overrides):
    defaults = {
        "suite": "smoke",
        "sample_root": None,
        "allow_missing_assets": False,
        "count": 24,
        "seed": 42,
        "timeout": 60,
        "report_json": None,
        "pytest_args": [],
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_suite_map_contains_public_commands() -> None:
    assert {"smoke", "unit", "assets", "quality", "acceptance", "all"} <= set(tool.PYTEST_SUITES)


def test_missing_sample_root_fails_asset_suite(tmp_path: Path) -> None:
    args = make_args(suite="assets", sample_root=str(tmp_path / "missing"))
    assert tool.run_pytest_suite(args) == 2


def test_allow_missing_sample_root_skips_asset_suite(tmp_path: Path) -> None:
    args = make_args(
        suite="assets",
        sample_root=str(tmp_path / "missing"),
        allow_missing_assets=True,
    )
    assert tool.run_pytest_suite(args) == 0


def test_pytest_args_are_forwarded(tmp_path: Path) -> None:
    args = make_args(
        suite="smoke",
        sample_root=str(tmp_path),
        pytest_args=["--", "-k", "core"],
    )
    completed = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=completed) as run:
        assert tool.run_pytest_suite(args) == 0
    cmd = run.call_args.args[0]
    assert "-k" in cmd
    assert "core" in cmd


def test_parse_cli_json_extracts_status_and_diagnostics() -> None:
    valid, status, diagnostics_count, stage = tool.parse_cli_json(json.dumps({
        "status": {"status": "partial"},
        "diagnostics": [{"module": "name_table"}],
    }))
    assert valid is True
    assert status == "partial"
    assert diagnostics_count == 1
    assert stage == "name_table"


def test_compat_report_json_schema(tmp_path: Path) -> None:
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    asset = sample_root / "A.uasset"
    asset.write_bytes(b"fake")
    report = tmp_path / "report.json"
    args = make_args(suite="compat", sample_root=str(sample_root), count=1, report_json=str(report))
    result = tool.CompatAssetResult(
        asset_path=str(asset),
        return_code=0,
        status="success",
        valid_json=True,
        diagnostics_count=0,
        failure_stage="",
        elapsed_seconds=0.01,
    )
    with patch("scripts.uasset_test.run_one_compat", return_value=result):
        assert tool.run_compat(args) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["suite"] == "compat"
    assert payload["summary"]["total"] == 1
    assert payload["results"][0]["valid_json"] is True
