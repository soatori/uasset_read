"""Golden public-format compatibility tests for Issue #518."""

import json
from pathlib import Path

import pytest

from uasset_read import parse_single


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "uasset_reader_js"
EXPECTED_BIGINTS = {
    "BP_Actor_Simple": ("20574n", "-1n"),
    "Actor": ("4613n", "4617n"),
}


@pytest.mark.parametrize("stem", ["BP_Actor_Simple", "Actor"])
def test_public_format_matches_pinned_fixture(stem: str) -> None:
    actual = json.loads(parse_single(
        str(FIXTURES / f"{stem}.uasset"),
        format="uasset-reader-js",
        log_enabled=False,
    ))
    expected = json.loads((FIXTURES / f"{stem}.json").read_text(encoding="utf-8"))

    assert list(expected) == ["header", "names", "gatherableTextData"]
    assert (
        expected["header"]["BulkDataStartOffset"],
        expected["header"]["PayloadTocOffset"],
    ) == EXPECTED_BIGINTS[stem]
    assert actual == expected
