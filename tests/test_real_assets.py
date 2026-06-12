from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.core import parse_single


pytestmark = pytest.mark.assets

FORMATS = [
    "json",
    "json_summary",
    "text",
    "markdown",
    "blueprint_text",
    "blueprint_ue_text",
    "cpp_skeleton",
]


@pytest.mark.parametrize("format_name", FORMATS)
def test_representative_asset_renders_non_empty(representative_asset: Path, format_name: str) -> None:
    output = parse_single(str(representative_asset), format=format_name, tolerant=True, max_file_size_mb=0)
    assert isinstance(output, str)
    assert output.strip()


def test_json_and_summary_agree_on_core_fields(representative_asset: Path) -> None:
    full = json.loads(parse_single(str(representative_asset), format="json", tolerant=True, max_file_size_mb=0))
    summary = json.loads(parse_single(str(representative_asset), format="json_summary", tolerant=True, max_file_size_mb=0))
    assert full["summary"]["package_name"] == summary["summary"]["package_name"]
    assert full["summary"]["total_export_count"] == summary["summary"]["total_export_count"]
    assert full["status"]["status"] in {"success", "partial", "failed"}


@pytest.mark.quality
def test_cpp_skeleton_quality_has_no_obvious_fallback_flood(blueprint_asset: Path) -> None:
    output = parse_single(str(blueprint_asset), format="cpp_skeleton", tolerant=True, max_file_size_mb=0)
    non_empty_lines = [line for line in output.splitlines() if line.strip()]
    assert non_empty_lines
    placeholder_count = output.count("Function_") + output.count("LocalFunction_")
    goto_count = output.count("goto Label_")
    assert placeholder_count / max(len(non_empty_lines), 1) < 0.25
    assert goto_count / max(len(non_empty_lines), 1) < 0.35
