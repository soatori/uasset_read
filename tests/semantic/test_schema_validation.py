"""Tests for semantic.schema.json — validates schema structure and completeness."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "semantic.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    """Load the semantic schema once per module."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_schema_loads(schema: dict) -> None:
    """Schema must declare Draft 2020-12."""
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_has_required_top_level(schema: dict) -> None:
    """All 8 required top-level fields must be present."""
    expected = ["format", "format_version", "mode", "asset", "references", "content", "coverage", "diagnostics"]
    assert schema["required"] == expected
    for field in expected:
        assert field in schema["properties"], f"Missing top-level property: {field}"


def test_schema_has_all_defs(schema: dict) -> None:
    """All 5 $defs must be defined."""
    expected_defs = ["AssetMeta", "ReferenceEntry", "ContentNode", "CoverageInfo", "DiagnosticEntry"]
    actual_defs = list(schema.get("$defs", {}).keys())
    for name in expected_defs:
        assert name in actual_defs, f"Missing $def: {name}"
