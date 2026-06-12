from __future__ import annotations

from pathlib import Path
import importlib
import json

import pytest

from uasset_read.core import list_formats, parse_single, parse_batch, ParseError
from uasset_read.cli import create_parser, resolve_format, _sanitize_error_message
from uasset_read.graph.flow_builder import format_graphs_json, format_node_dict
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.models.blueprint import BlueprintMetadata
from uasset_read.models.core import FEdGraphPinType, UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.models.result import ParseResult
from uasset_read.package import FileSystemPackageProvider
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker

pytestmark = pytest.mark.auxiliary


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


def test_listed_cli_formats_are_parseable():
    """所有 list_formats() 返回的格式名都能被 CLI 参数解析。"""
    parser = create_parser()

    for fmt in list_formats():
        parser.parse_args([f"--{fmt.replace('_', '-')}", "Asset.uasset"])


def test_cli_error_sanitizer_handles_paths_with_spaces():
    message = (
        r"failed opening C:\Users\me\Top Secret\Nested Dir\asset.uasset: denied; "
        r"unc=\\server\share\Sensitive Folder\other.umap failed; "
        "unix=/home/me/Secret Folder/asset.pak: bad"
    )

    sanitized = _sanitize_error_message(message)

    assert "asset.uasset" in sanitized
    assert "other.umap" in sanitized
    assert "asset.pak" in sanitized
    assert "Top Secret" not in sanitized
    assert "Nested Dir" not in sanitized
    assert "Sensitive Folder" not in sanitized
    assert "Secret Folder" not in sanitized


def test_cli_error_sanitizer_keeps_context_between_unix_paths():
    message = (
        "trace /home/me/Secret Folder/asset.pak and "
        "/tmp/Other Folder/out.json done"
    )

    sanitized = _sanitize_error_message(message)

    assert "asset.pak" in sanitized
    assert "out.json" in sanitized
    assert " and " in sanitized
    assert " done" in sanitized
    assert "Secret Folder" not in sanitized
    assert "Other Folder" not in sanitized


def test_cli_error_sanitizer_preserves_unix_path_line_number():
    sanitized = _sanitize_error_message(
        "/home/me/Secret Folder/asset.pak:12: bad"
    )

    assert sanitized == "asset.pak:12: bad"
    assert "Secret Folder" not in sanitized


def test_cli_error_sanitizer_leaves_non_path_messages_readable():
    assert _sanitize_error_message("ParseError: invalid export count") == (
        "ParseError: invalid export count"
    )


def test_parse_uasset_with_linker_uses_provider():
    class _ProviderThatRaises:
        def __init__(self):
            self.used = False

        def open_package_bundle(self, path: str, tolerant: bool = False):
            self.used = True
            raise RuntimeError(f"provider used for {path}")

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


def test_source_files_do_not_have_utf8_bom():
    root = Path(__file__).resolve().parents[1] / "src" / "uasset_read"
    offenders = [
        str(path.relative_to(root.parent.parent))
        for path in root.rglob("*.py")
        if path.read_bytes().startswith(b"\xef\xbb\xbf")
    ]

    assert offenders == []


def test_root_parse_uasset_name_shadows_module_compatibly():
    import uasset_read
    import uasset_read.parse_uasset as maybe_function

    module = importlib.import_module("uasset_read.parse_uasset")

    assert maybe_function is uasset_read.parse_uasset
    assert hasattr(module, "parse_package")


def test_iostore_directory_index_list_files_is_stable_when_unparsed():
    reader = IoStoreReader("dummy.utoc")
    reader._directory_index_buffer = b"raw-directory-index"

    assert reader.list_files() == []
