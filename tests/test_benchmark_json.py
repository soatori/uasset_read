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

    is_blueprint = payload.get("format") == "uasset_read.blueprint_semantic"

    # Common keys present in both formats
    common_keys = {
        "format",
        "format_version",
        "mode",
        "asset_type",
        "asset",
        "status",
    }
    assert common_keys <= payload.keys()
    assert isinstance(payload["status"], dict)
    assert payload["status"].get("parse") in {"complete", "partial", "failed"}

    if is_blueprint:
        # Blueprint format carries declarations instead of raw references
        assert "declaration" in payload or "components" in payload
    else:
        assert "references" in payload
        assert isinstance(payload["references"], list)
        assert "diagnostics" in payload
        assert isinstance(payload["diagnostics"], list)
