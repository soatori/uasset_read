"""Golden public-format compatibility tests for Issue #518."""

import json
from pathlib import Path
import struct
import sys

import pytest

from uasset_read import list_formats, parse_single
from uasset_read.cli import create_parser, main, resolve_format
from uasset_read.compat.uasset_reader_js import (
    _bigint_json_string,
    _guid_slot_to_js,
    render_uasset_reader_js,
)
from uasset_read.exceptions import ParseError
from uasset_read.project_logging import get_last_parse_result


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "uasset_reader_js"
SAMPLES = Path(__file__).resolve().parent / "samples"
EXPECTED_BIGINTS = {
    "BP_Actor_Simple": ("20574n", "-1n"),
    "Actor": ("4613n", "4617n"),
}
NORMAL_JSON_ROOT_KEYS = {
    "status",
    "metadata",
    "summary",
    "exports",
    "import_map",
    "name_map",
    "blueprint",
    "variables",
    "warnings",
    "diagnostics",
    "asset_registry_data",
    "statistics",
}


def test_cli_selects_uasset_reader_js_format() -> None:
    args = create_parser().parse_args([
        "--format",
        "uasset-reader-js",
        "asset.uasset",
    ])

    assert resolve_format(args) == "uasset-reader-js"


def test_public_format_discovery_includes_uasset_reader_js() -> None:
    assert "uasset-reader-js" in list_formats()


def test_cli_format_discovery_shows_usable_uasset_reader_js_invocation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["uasset_read", "--list-formats"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "  --format uasset-reader-js\n" in output
    assert "--uasset-reader-js" not in output


def test_normal_json_root_keys_are_unchanged() -> None:
    actual = json.loads(parse_single(
        str(FIXTURES / "BP_Actor_Simple.uasset"),
        format="json",
        log_enabled=False,
    ))

    assert set(actual) == NORMAL_JSON_ROOT_KEYS


def test_js_guid_slot_reverses_each_u32_and_uppercases() -> None:
    assert (
        _guid_slot_to_js(bytes.fromhex("dd75e5292746a3e076d2109deadc2c23"))
        == "29E575DDE0A346279D10D276232CDCEA"
    )


def test_bigint_json_string_keeps_sign() -> None:
    assert _bigint_json_string(-1) == "-1n"


@pytest.mark.parametrize("stem", ["BP_Actor_Simple", "Actor"])
def test_direct_reader_matches_pinned_fixture(stem: str) -> None:
    expected = json.loads((FIXTURES / f"{stem}.json").read_text(encoding="utf-8"))

    actual = json.loads(render_uasset_reader_js(str(FIXTURES / f"{stem}.uasset")))

    assert actual == expected


def test_direct_reader_rejects_ue5_import_type_hierarchies(
    tmp_path: Path,
) -> None:
    data = bytearray((FIXTURES / "Actor.uasset").read_bytes())
    data[16:20] = struct.pack("<i", 1018)
    path = tmp_path / "ue5-1018.uasset"
    path.write_bytes(data)

    with pytest.raises(ParseError, match="FileVersionUE5"):
        render_uasset_reader_js(str(path))


def test_direct_reader_rejects_source_string_metadata(tmp_path: Path) -> None:
    data = bytearray((FIXTURES / "BP_Actor_Simple.uasset").read_bytes())
    data[2989:2993] = struct.pack("<i", 1)
    path = tmp_path / "source-string-metadata.uasset"
    path.write_bytes(data)

    with pytest.raises(ParseError, match="SourceStringMetaData.ValueCount"):
        render_uasset_reader_js(str(path))


@pytest.mark.parametrize("stem", ["BP_Actor_Simple", "Actor"])
def test_public_format_matches_pinned_fixture(stem: str) -> None:
    expected = json.loads((FIXTURES / f"{stem}.json").read_text(encoding="utf-8"))

    assert list(expected) == ["header", "names", "gatherableTextData"]
    assert (
        expected["header"]["BulkDataStartOffset"],
        expected["header"]["PayloadTocOffset"],
    ) == EXPECTED_BIGINTS[stem]
    assert expected["names"]
    assert all(
        set(name) == {"Name", "NonCasePreservingHash", "CasePreservingHash"}
        for name in expected["names"]
    )

    actual = json.loads(parse_single(
        str(FIXTURES / f"{stem}.uasset"),
        format="uasset-reader-js",
        log_enabled=False,
    ))
    assert actual == expected


def test_public_format_cleans_transient_export_data_after_rendering() -> None:
    path = SAMPLES / "FirstPerson_M_FlatCol.uasset"
    expected = render_uasset_reader_js(str(path))

    actual = parse_single(
        str(path),
        format="uasset-reader-js",
        log_enabled=False,
    )
    result = get_last_parse_result()

    assert actual == expected
    assert result.status == "partial"
    assert result.export_map
    assert all(
        not hasattr(export, "_asset_type_data")
        and not hasattr(export, "_uclass_native_fields")
        for export in result.export_map
    )
