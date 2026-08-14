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
        "format",
        "format_version",
        "mode",
        "asset_type",
        "asset",
        "status",
        "references",
        "diagnostics",
    }
    assert required_keys <= payload.keys()
    assert isinstance(payload["status"], dict)
    assert payload["status"].get("parse") in {"complete", "partial", "failed"}
    assert isinstance(payload["references"], list)
    assert isinstance(payload["diagnostics"], list)
