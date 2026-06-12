from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.core import parse_single


pytestmark = pytest.mark.assets

FORMATS = [
    "json",
    "markdown",
]


@pytest.mark.parametrize("format_name", FORMATS)
def test_representative_asset_renders_non_empty(representative_asset: Path, format_name: str) -> None:
    output = parse_single(str(representative_asset), format=format_name, tolerant=True, max_file_size_mb=0)
    assert isinstance(output, str)
    assert output.strip()


def test_json_renders_core_fields(representative_asset: Path) -> None:
    full = json.loads(parse_single(str(representative_asset), format="json", tolerant=True, max_file_size_mb=0))
    assert full["summary"]["package_name"]
    assert full["summary"]["total_export_count"]
    assert full["status"]["status"] in {"success", "partial", "failed"}
