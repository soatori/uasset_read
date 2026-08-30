"""Schema contract — validate projection output against JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # required test dependency; collection fails fast if missing
import pytest

SCHEMA_PATH = Path(__file__).parent.parent.parent / "docs" / "designs" / "contract" / "package_document_v2.schema.json"
EXAMPLE_PATH = (
    Path(__file__).parent.parent.parent / "docs" / "designs" / "contract" / "package_document_v2.example.json"
)
SAMPLES_DIR = Path(__file__).parent.parent / "samples"
SAMPLE = str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def doc():
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(SAMPLE)


class TestSchemaValidation:
    def test_example_validates_against_schema(self, schema):
        """The checked contract example must validate against the schema."""
        with open(EXAMPLE_PATH) as f:
            example = json.load(f)

        jsonschema.validate(example, schema)

    def test_projection_output_validates(self, schema, doc):
        """A real projection output must validate against the schema."""
        from uasset_read.v2.projection import project_document

        result = project_document(doc, view="semantic", depth="asset", limit=3)
        jsonschema.validate(result, schema)

    def test_all_views_validate(self, schema, doc):
        """All view types must produce valid output."""
        from uasset_read.v2.projection import project_document

        for view in ("semantic", "raw", "debug"):
            result = project_document(doc, view=view, depth="asset", limit=2)
            jsonschema.validate(result, schema)

    def test_schema_has_required_fields(self, schema):
        """Schema must define all required top-level fields."""
        required = set(schema.get("required", []))
        assert "format" in required
        assert "format_version" in required
        assert "view" in required
        assert "depth" in required
        assert "source" in required
        assert "package" in required
        assert "objects" in required
        assert "relations" in required
        assert "dependencies" in required
        assert "payloads" in required
        assert "diagnostics" in required
        assert "summary" in required

    def test_schema_enums_match_code(self, schema):
        """Schema enums must match the code's valid values."""
        view_enum = schema["properties"]["view"]["enum"]
        assert set(view_enum) == {"semantic", "raw", "debug"}

        depth_enum = schema["properties"]["depth"]["enum"]
        assert set(depth_enum) == {"package", "object", "asset", "decode"}
