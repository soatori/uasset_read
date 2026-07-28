"""Acceptance coverage for the standard JSON output contract (#510)."""

import json
from pathlib import Path

import jsonschema

from uasset_read import parse_single


SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
FIXED_TOP_LEVEL_FIELDS = {
    "metadata": dict,
    "import_map": list,
    "name_map": list,
    "warnings": list,
    "diagnostics": list,
    "statistics": dict,
}


def _parse_standard_sample(name: str) -> dict:
    return json.loads(parse_single(str(SAMPLES_DIR / name), format="json", tolerant=True))


def test_standard_json_has_fixed_contract_fields() -> None:
    """Standard JSON always exposes its fixed top-level contract fields."""
    data = _parse_standard_sample("ALS_AnimBP.uasset")

    for field, expected_type in FIXED_TOP_LEVEL_FIELDS.items():
        assert field in data, f"missing {field}"
        assert isinstance(data[field], expected_type), f"{field} has wrong type"


def test_all_standard_sample_outputs_validate_against_schema() -> None:
    """Every bundled sample's standard JSON conforms to the published schema."""
    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas" / "package.schema.json").read_text(encoding="utf-8"))

    for sample in sorted(SAMPLES_DIR.glob("*.uasset")):
        jsonschema.validate(_parse_standard_sample(sample.name), schema)
