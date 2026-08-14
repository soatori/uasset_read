"""Benchmark the user-visible JSON output contract."""

import json

import pytest

from uasset_read import parse_single


@pytest.mark.benchmark
def test_json_output_public_contract(blueprint_sample, measure):
    with measure("json"):
        output = parse_single(
            str(blueprint_sample),
            format="json",
            tolerant=True,
            force_full_parse=True,
        )
        payload = json.loads(output)

    required_keys = {
        "status",
        "summary",
        "exports",
        "function_graphs",
        "variables",
        "warnings",
        "diagnostics",
        "statistics",
    }
    assert required_keys <= payload.keys()
    assert isinstance(payload["status"], dict)
    assert payload["status"].get("status") in {"success", "partial"}
    assert payload["exports"]
    assert payload["function_graphs"]
    assert payload["variables"]
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["diagnostics"], list)
    assert isinstance(payload["statistics"], dict)
