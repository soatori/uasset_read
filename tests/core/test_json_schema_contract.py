"""JSON contract acceptance coverage for #507, #509, and #510.

Exercises standard/debug output across all bundled samples against the
published schema.
"""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from jsonschema import ValidationError

from uasset_read import parse_single


SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "package.schema.json"
FIXED_TOP_LEVEL_FIELDS = {
    "metadata": dict,
    "import_map": list,
    "name_map": list,
    "warnings": list,
    "diagnostics": list,
    "statistics": dict,
}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _parse_sample(name: str, output_level: str = "standard") -> dict:
    return json.loads(parse_single(
        str(SAMPLES_DIR / name), format="json", tolerant=True, output_level=output_level,
    ))


def _parse_standard_sample(name: str) -> dict:
    return _parse_sample(name)


def test_standard_json_has_fixed_contract_fields() -> None:
    """Standard JSON always exposes its fixed top-level contract fields."""
    data = _parse_standard_sample("ALS_AnimBP.uasset")

    for field, expected_type in FIXED_TOP_LEVEL_FIELDS.items():
        assert field in data, f"missing {field}"
        assert isinstance(data[field], expected_type), f"{field} has wrong type"


def test_all_standard_and_debug_sample_outputs_validate_against_schema() -> None:
    """Every bundled sample's standard and debug JSON conforms to the schema."""
    schema = _schema()

    for sample in sorted(SAMPLES_DIR.glob("*.uasset")):
        for output_level in ("standard", "debug"):
            jsonschema.validate(_parse_sample(sample.name, output_level), schema)


def test_schema_rejects_graph_without_nodes() -> None:
    data = _parse_sample("FirstPerson_BP_FirstPersonCharacter.uasset")
    graph = next(graph for export in data["exports"] for graph in export.get("graphs", []))
    graph.pop("nodes")
    with pytest.raises(ValidationError):
        jsonschema.validate(data, _schema())


def test_schema_rejects_empty_diagnostic_object() -> None:
    data = copy.deepcopy(_parse_standard_sample("ALS_AnimBP.uasset"))
    data["diagnostics"] = [{}]
    with pytest.raises(ValidationError):
        jsonschema.validate(data, _schema())
