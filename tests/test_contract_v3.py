from pathlib import Path
import copy
import json

import jsonschema
import pytest

from tests.fixtures import parse_sample
from uasset_read.projection import project_document

_CONTRACT_DIR = Path(__file__).resolve().parents[1] / "docs" / "designs" / "contract"


def test_rebuilt_document_declares_v3_and_package_first():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="package")
    output = project_document(document, depth="package")
    assert output["format_version"] == "3.0"
    assert isinstance(output["projections"], list)
    assert isinstance(output["sidecars"], list)
    assert document.objects
    assert all(obj.id.startswith(("export:", "import:")) for obj in document.objects)


def test_stackobot_package_counts_match_manifest():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="package")
    assert len(document.objects) == 31
    assert document.package.export_count == 31


def _v3_schema_and_example():
    schema = json.loads((_CONTRACT_DIR / "package_document_v3.schema.json").read_text(encoding="utf-8"))
    example = json.loads((_CONTRACT_DIR / "package_document_v3.example.json").read_text(encoding="utf-8"))
    return schema, example


def _sidecar_record():
    return {
        "path": "projections/export_1.cpp",
        "size": 128,
        "sha256": "a" * 64,
        "reason": "size boundary",
        "source_range": {"offset": 128, "size": 64},
    }


def test_projection_record_requires_provenance_when_embedded():
    """Brief: every embedded projection has capability/status and provenance — schema-enforced."""
    schema, example = _v3_schema_and_example()
    jsonschema.validate(example, schema)  # positive: shipped example carries provenance

    missing = copy.deepcopy(example)
    missing["projections"][0].pop("provenance")
    # oneOf reports the sibling branch's failure, so assert rejection itself,
    # not the message text.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(missing, schema)


def test_projection_record_content_and_external_are_exclusive():
    """Either embedded content or an external sidecar reference — never both."""
    schema, example = _v3_schema_and_example()

    # embedded=true record must not also carry an external sidecar reference.
    embedded_plus_external = copy.deepcopy(example)
    embedded_plus_external["projections"][0]["external"] = _sidecar_record()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(embedded_plus_external, schema)

    # embedded=false record must not carry content.
    external_plus_content = copy.deepcopy(example)
    record = external_plus_content["projections"][0]
    record["embedded"] = False
    record["external"] = _sidecar_record()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(external_plus_content, schema)

    # external-only record (no content, no provenance required) validates.
    external_only = copy.deepcopy(example)
    record = external_only["projections"][0]
    record.pop("content")
    record.pop("provenance")
    record["embedded"] = False
    record["external"] = _sidecar_record()
    jsonschema.validate(external_only, schema)
