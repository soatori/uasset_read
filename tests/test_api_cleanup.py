from __future__ import annotations

from pathlib import Path
import importlib
import json

import pytest

from uasset_read.cli import _build_export_options, _handle_graph_mode, create_parser
from uasset_read.exporter.batch import BatchExporter
from uasset_read.exporter.base import ExportOptions
from uasset_read.exporter import ExporterRegistry
from uasset_read.graph.flow_builder import format_graphs_json, format_node_dict
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.models.blueprint import BlueprintMetadata
from uasset_read.models.core import FEdGraphPinType, UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.models.result import ParseResult
from uasset_read.package import FileSystemPackageProvider
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker


def test_format_graphs_json_minimal_graph_does_not_crash():
    graph = UEdGraph(
        graph_name="EventGraph",
        graph_class="EdGraph",
        nodes=[UEdGraphNode(node_guid="node-1", class_name="K2Node_Event")],
    )

    payload = format_graphs_json([graph])

    assert payload[0]["graph_name"] == "EventGraph"
    assert payload[0]["nodes"][0]["node_name"] == "K2Node_Event_0"


def test_format_node_dict_comment_fields():
    node = UEdGraphNode(
        node_guid="comment-1",
        class_name="EdGraphNode_Comment",
        node_comment="Note",
        node_data={"node_width": 300, "node_height": 120, "font_size": 18},
    )

    payload = format_node_dict(node, 2)

    assert payload["comment"] == {
        "text": "Note",
        "width": 300,
        "height": 120,
        "font_size": 18,
    }


def test_format_node_dict_call_function_parameters():
    node = UEdGraphNode(
        node_guid="call-1",
        class_name="K2Node_CallFunction",
        pins=[
            UEdGraphPin(
                pin_id="pin-in",
                pin_name="Value",
                direction=0,
                pin_type=FEdGraphPinType(pin_category="float"),
                default_value="1.0",
            ),
            UEdGraphPin(
                pin_id="pin-out",
                pin_name="ReturnValue",
                direction=1,
                pin_type=FEdGraphPinType(pin_category="bool"),
            ),
        ],
    )

    payload = format_node_dict(node, 0)

    assert payload["parameters"]["input_params"][0]["name"] == "Value"
    assert payload["parameters"]["output_params"][0]["name"] == "ReturnValue"


def test_listed_cli_formats_are_parseable():
    parser = create_parser()

    for fmt in ExporterRegistry.list_formats():
        parser.parse_args([f"--{fmt.replace('_', '-')}", "Asset.uasset"])


def test_build_export_options_keeps_linker_json_flags():
    parser = create_parser()
    args = parser.parse_args([
        "--json",
        "--schema",
        "--function-graphs",
        "--verbose",
        "--validate",
        "--strict",
        "--include-parent-assets",
        "--asset-root",
        "Content",
        "Asset.uasset",
    ])

    options = _build_export_options(args, "json")

    assert options.include_schema is True
    assert options.include_function_graphs is True
    assert options.verbose is True
    assert options.validate_output is True
    assert options.tolerant is False
    assert options.include_parent_assets is True
    assert options.asset_roots == ["Content"]


def test_graph_mode_json_summary_uses_summary_formatter(capsys):
    parser = create_parser()
    args = parser.parse_args(["--graph", "--json-summary", "Asset.uasset"])
    result = ParseResult()

    _handle_graph_mode(args, result)

    payload = json.loads(capsys.readouterr().out)
    assert payload["output_version"] == "4.0"
    assert "graphs" not in payload


def test_graph_mode_summary_alias_uses_json_summary(capsys):
    parser = create_parser()
    args = parser.parse_args(["--graph", "--summary", "Asset.uasset"])
    result = ParseResult()

    _handle_graph_mode(args, result)

    payload = json.loads(capsys.readouterr().out)
    assert payload["output_version"] == "4.0"
    assert "graphs" not in payload


def test_graph_mode_text_summary_uses_text_summary(capsys):
    parser = create_parser()
    args = parser.parse_args(["--graph", "--text-summary", "Asset.uasset"])
    result = ParseResult()

    _handle_graph_mode(args, result)

    output = capsys.readouterr().out
    assert "Package:" in output
    assert '"graphs"' not in output


def test_source_files_do_not_have_utf8_bom():
    root = Path(__file__).resolve().parents[1] / "src" / "uasset_read"
    offenders = [
        str(path.relative_to(root.parent.parent))
        for path in root.rglob("*.py")
        if path.read_bytes().startswith(b"\xef\xbb\xbf")
    ]

    assert offenders == []


class _ProviderThatRaises:
    def __init__(self):
        self.used = False

    def open_package_bundle(self, path: str, tolerant: bool = False):
        self.used = True
        raise RuntimeError(f"provider used for {path}")


def test_parse_uasset_with_linker_uses_provider():
    provider = _ProviderThatRaises()

    result = parse_uasset_with_linker("Game/A.uasset", provider=provider)

    assert provider.used
    assert not result.is_success
    assert "provider used for Game/A.uasset" in result.errors[0]


def test_parse_package_rejects_unused_aes_key():
    result = parse_package("Game/A.uasset", aes_key=b"0" * 16)

    assert not result.is_success
    assert "Unsupported argument: aes_key" in result.errors[0]
    assert "Unexpected error" not in result.errors[0]


def test_filesystem_provider_supports_root_relative_paths(tmp_path: Path):
    asset_dir = tmp_path / "Game"
    asset_dir.mkdir()
    asset = asset_dir / "A.uasset"
    asset.write_bytes(b"asset")

    bundle = FileSystemPackageProvider(tmp_path).open_package_bundle("Game/A.uasset")

    assert bundle.main_path == str(asset)


def test_root_parse_uasset_name_shadows_module_compatibly():
    import uasset_read
    import uasset_read.parse_uasset as maybe_function

    module = importlib.import_module("uasset_read.parse_uasset")

    assert maybe_function is uasset_read.parse_uasset
    assert hasattr(module, "parse_package")


class _Archive:
    _byte_swapping = False

    def get_mmap_info(self):
        return {"used": False, "warning": None}

    def close(self):
        pass


class _Bundle:
    package_kind = "asset"
    package_files = {".uasset": "<test>"}
    container = "test"

    def open_archive(self, tolerant: bool = False):
        return _Archive()


class _Provider:
    def open_package_bundle(self, path: str, tolerant: bool = False):
        return _Bundle()


class _Export:
    serial_size = 1
    object_name = "BrokenExport"
    class_index = None
    outer_index = None
    serial_offset = 0


class _MockLinker:
    def link(self): pass
    def post_load(self): pass


def test_strict_property_parse_error_is_fatal(monkeypatch):
    parser_module = importlib.import_module("uasset_read.parse_uasset")

    monkeypatch.setattr(parser_module, "read_package_summary", lambda archive: object())
    monkeypatch.setattr(parser_module, "build_version_container", lambda summary: object())
    monkeypatch.setattr(parser_module, "read_name_table", lambda archive, summary: ["Asset"])
    monkeypatch.setattr(parser_module, "read_import_map", lambda archive, summary, names: [])
    monkeypatch.setattr(parser_module, "read_export_map", lambda archive, summary, names: [_Export()])
    monkeypatch.setattr(
        parser_module,
        "parse_properties_from_export",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad property")),
    )
    monkeypatch.setattr(parser_module, "_post_process", lambda *args, **kwargs: None)

    # Mock PackageLinker at its source module (test focuses on property parse error, not linker)
    from uasset_read.link import linker as linker_mod
    monkeypatch.setattr(linker_mod, "PackageLinker", lambda *a, **kw: _MockLinker())

    result = parse_package("Game/A.uasset", tolerant=False, provider=_Provider())

    assert not result.is_success
    assert result.errors == ["Property parse error in BrokenExport: bad property"]


def test_batch_exporter_passes_parse_options(monkeypatch, tmp_path: Path):
    calls = []

    class _Result:
        is_success = False

    def fake_parse_package(path, **kwargs):
        calls.append((path, kwargs))
        return _Result()

    parser_module = importlib.import_module("uasset_read.parse_uasset")
    monkeypatch.setattr(parser_module, "parse_package", fake_parse_package)

    options = ExportOptions(
        format="text",
        tolerant=False,
        include_parent_assets=True,
        asset_roots=["Content"],
    )
    exporter = BatchExporter(str(tmp_path / "out"), options)

    result = exporter.export_files(["Asset.uasset"])

    assert result.skipped == [("Asset.uasset", "parse failed")]
    assert calls == [(
        "Asset.uasset",
        {
            "tolerant": False,
            "include_parent_assets": True,
            "asset_roots": ["Content"],
        },
    )]


def test_batch_options_from_cli_include_parse_flags():
    parser = create_parser()
    args = parser.parse_args([
        "--batch",
        "--strict",
        "--include-parent-assets",
        "--asset-root",
        "Content",
        "Assets",
    ])

    options = _build_export_options(args, "text", output_dir="Assets/output")

    assert options.tolerant is False
    assert options.include_parent_assets is True
    assert options.asset_roots == ["Content"]


def test_iostore_directory_index_list_files_is_stable_when_unparsed():
    reader = IoStoreReader("dummy.utoc")
    reader._directory_index_buffer = b"raw-directory-index"

    assert reader.list_files() == []


def test_blueprint_metadata_from_archive_error_is_actionable():
    with pytest.raises(NotImplementedError, match="extract_blueprint_metadata"):
        BlueprintMetadata.from_archive(None)
