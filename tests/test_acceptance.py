from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.core import parse_single


pytestmark = pytest.mark.acceptance


def test_blueprint_asset_json_has_project_goal_fields(blueprint_asset: Path) -> None:
    data = json.loads(parse_single(str(blueprint_asset), format="json", tolerant=True, max_file_size_mb=0))
    assert data["status"]["status"] in {"success", "partial"}
    assert data["summary"]["package_name"]
    assert isinstance(data.get("exports", []), list)
    assert "decompiled_functions" in data


def test_diagnostics_are_structured_when_present(blueprint_asset: Path) -> None:
    data = json.loads(parse_single(str(blueprint_asset), format="json", tolerant=True, max_file_size_mb=0))
    diagnostics = data.get("diagnostics", [])
    assert isinstance(diagnostics, list)
    for diagnostic in diagnostics:
        assert isinstance(diagnostic, dict)
        assert any(key in diagnostic for key in ("module", "field", "stage", "message", "error"))


def test_core_formats_keep_same_package_identity(blueprint_asset: Path) -> None:
    json_data = json.loads(parse_single(str(blueprint_asset), format="json", tolerant=True, max_file_size_mb=0))
    package_name = json_data["summary"]["package_name"].rsplit("/", 1)[-1]
    for format_name in ["markdown"]:
        output = parse_single(str(blueprint_asset), format=format_name, tolerant=True, max_file_size_mb=0)
        assert output.strip()
        assert package_name in output or json_data["summary"]["package_name"] in output


def test_known_gap_does_not_report_complete_success(all_assets: list[Path]) -> None:
    legacy = next((p for p in all_assets if p.name.lower() == "p_fire.uasset"), None)
    if legacy is None:
        pytest.skip("Known UE4 legacy sample P_Fire.uasset not available")
    data = json.loads(parse_single(str(legacy), format="json", tolerant=True, max_file_size_mb=0))
    assert data["status"]["status"] in {"partial", "failed"}
