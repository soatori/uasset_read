"""core.py API 测试。

合并测试文件：
- test_core_api.py — core API 测试
- test_api_cleanup.py — API 清理与辅助功能测试
"""
from __future__ import annotations

from pathlib import Path
import importlib
import json

import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from uasset_read.core import (
    BatchResult,
    ParseError,
    _can_render_tolerant_json,
    list_formats,
    parse_batch,
    parse_single,
)
from uasset_read.cli import create_parser, resolve_format, _sanitize_error_message
from uasset_read.graph.flow_builder import format_graphs_json, format_node_dict
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.models.blueprint import BlueprintMetadata
from uasset_read.models.core import FEdGraphPinType, UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.models.result import ParseResult
from uasset_read.package import FileSystemPackageProvider
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker


class TestListFormats:
    def test_json_in_formats(self):
        fmts = list_formats()
        assert "json" in fmts

    def test_markdown_in_formats(self):
        fmts = list_formats()
        assert "markdown" in fmts


class TestParseSingle:
    def test_bare_magic_mock_is_not_a_renderable_partial_result(self):
        mock_result = MagicMock()
        mock_result.is_success = False
        mock_result.errors = ["test error"]

        assert _can_render_tolerant_json(mock_result, "json", True) is False

    def test_parse_single_raises_on_parse_failure(self):
        """parse_single 在解析失败时抛出 ParseError。"""
        from uasset_read.link.result import LinkerParseResult

        with patch("uasset_read.core.parse_uasset_with_linker") as mock_parse:
            mock_parse.return_value = LinkerParseResult(
                is_success=False,
                errors=["test error"],
            )

            with pytest.raises(ParseError, match="Parse failed"):
                parse_single("nonexistent.uasset", format="json")

    def test_parse_single_raises_on_render_failure(self):
        """parse_single 在渲染器不存在时抛出 ValueError。"""
        with patch("uasset_read.core.parse_package") as mock_parse:
            mock_result = MagicMock()
            mock_result.is_success = True
            mock_parse.return_value = mock_result
            with patch("uasset_read.core.build_package_ir") as mock_build:
                mock_ir = MagicMock()
                mock_build.return_value = mock_ir
                with pytest.raises(ValueError):
                    parse_single("test.uasset", format="nonexistent_format")

    def test_parse_single_uses_linker_for_json_format(self):
        """parse_single 对 json 格式使用 parse_uasset_with_linker。"""
        with patch("uasset_read.core.parse_uasset_with_linker") as mock_linker_parse:
            mock_result = MagicMock()
            mock_result.is_success = True
            mock_linker_parse.return_value = mock_result
            with patch("uasset_read.core.build_package_ir") as mock_build:
                mock_ir = MagicMock()
                mock_build.return_value = mock_ir
                with patch("uasset_read.core.get_renderer") as mock_get_renderer:
                    mock_renderer = MagicMock()
                    mock_renderer.render.return_value = "{}"
                    mock_get_renderer.return_value = mock_renderer

                    parse_single("test.uasset", format="json")
                    mock_linker_parse.assert_called_once()

    def test_parse_single_forwards_memory_policy(self):
        from uasset_read.memory_safety import MemoryPolicy

        policy = MemoryPolicy()
        result = MagicMock()
        result.is_success = True

        with patch(
            "uasset_read.core.parse_uasset_with_linker",
            return_value=result,
        ) as mock_parse, patch(
            "uasset_read.core.build_package_ir",
            return_value=MagicMock(),
        ), patch("uasset_read.core.get_renderer") as mock_get_renderer:
            mock_get_renderer.return_value.render.return_value = "{}"

            parse_single("test.uasset", format="json", memory_policy=policy)

        assert mock_parse.call_args.kwargs["memory_policy"] is policy


class TestParseBatch:
    def test_parse_batch_isolates_each_asset_and_continues_after_failure(
        self,
        tmp_path,
    ):
        first = tmp_path / "a.uasset"
        second = tmp_path / "b.uasset"
        first.write_bytes(b"a")
        second.write_bytes(b"b")
        first_output = tmp_path / "out" / "a.json"

        outcomes = [
            SimpleNamespace(
                succeeded=True,
                output_path=str(first_output),
                error="",
            ),
            SimpleNamespace(
                succeeded=False,
                output_path="",
                error="memory_limit: 1025.0MB > 1024.0MB",
            ),
        ]
        with patch(
            "uasset_read.core.run_isolated_asset",
            create=True,
            side_effect=outcomes,
        ) as run_isolated:
            result = parse_batch(
                str(tmp_path),
                output_dir=str(tmp_path / "out"),
            )

        assert run_isolated.call_count == 2
        first_request = run_isolated.call_args_list[0].args[0]
        assert first_request.parse_options["include_parent_assets"] is None
        assert "memory_policy" in first_request.parse_options
        assert result.success == [str(first_output)]
        assert result.failed == [
            (str(second), "memory_limit: 1025.0MB > 1024.0MB")
        ]
        assert result.skipped == []

    def test_parse_batch_warns_for_deprecated_skip_large_files(self, tmp_path):
        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)

        with patch(
            "uasset_read.core.run_isolated_asset",
            create=True,
            return_value=SimpleNamespace(
                succeeded=True,
                output_path=str(tmp_path / "output" / "test.json"),
                error="",
            ),
        ), pytest.warns(DeprecationWarning, match="skip_large_files"):
            parse_batch(str(tmp_path), skip_large_files=True)

    def test_parse_batch_stops_launching_workers_at_system_memory_limit(
        self,
        tmp_path,
    ):
        for name in ("a.uasset", "b.uasset"):
            (tmp_path / name).write_bytes(b"x")

        with patch(
            "uasset_read.memory_safety.get_memory_stats",
        ) as get_stats, patch(
            "uasset_read.core.run_isolated_asset",
        ) as run_isolated:
            get_stats.return_value = SimpleNamespace(usage_percent=0.9)
            result = parse_batch(str(tmp_path), max_memory_usage=0.85)

        run_isolated.assert_not_called()
        assert len(result.skipped) == 2
        assert all("90.0% exceeds 85.0%" in reason for _, reason in result.skipped)

    def test_parse_batch_raises_on_non_directory(self):
        """parse_batch 在非目录输入时抛出 ValueError。"""
        with pytest.raises(ValueError, match="Not a directory"):
            parse_batch("nonexistent_directory")

    def test_parse_batch_raises_on_empty_directory(self, tmp_path):
        """parse_batch 在空目录时抛出 ValueError。"""
        with pytest.raises(ValueError, match="No .uasset/.umap files found"):
            parse_batch(str(tmp_path))

    def test_parse_batch_returns_batch_result(self, tmp_path):
        """parse_batch 返回 BatchResult。"""
        # 创建一个临时 .uasset 文件
        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)  # dummy data

        with patch("uasset_read.core.parse_single") as mock_parse_single:
            mock_parse_single.return_value = '{"status": "success"}'

            result = parse_batch(
                str(tmp_path),
                format="json",
                isolate_assets=False,
            )

            assert isinstance(result, BatchResult)
            assert result.total == 1

    def test_parse_batch_handles_failures(self, tmp_path):
        """parse_batch 正确处理失败文件。"""
        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)

        with patch("uasset_read.core.parse_single") as mock_parse_single:
            mock_parse_single.side_effect = ParseError("test error")

            result = parse_batch(
                str(tmp_path),
                format="json",
                isolate_assets=False,
            )

            assert result.total == 1
            assert len(result.failed) == 1
            assert len(result.success) == 0


class TestCLIBatchOptions:
    """验证 CLI batch 模式传递所有输出选项给 parse_batch。"""

    def test_batch_passes_all_options(self, tmp_path):
        """CLI batch 应传递 verbose/schema/function_graphs/parent_assets 等选项。"""
        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)

        with patch("uasset_read.core.parse_single") as mock_parse_single:
            mock_parse_single.return_value = '{"status": "success"}'

            # 模拟 CLI 调用 parse_batch 时传递所有选项
            result = parse_batch(
                str(tmp_path),
                format="json",
                output_dir=str(tmp_path / "out"),
                tolerant=True,
                verbose=True,
                include_schema=True,
                include_function_graphs=True,
                include_parent_assets=True,
                asset_roots=["/game/root"],
                mappings_path="test.usmap",
                game="Fortnite",
                isolate_assets=False,
            )

            assert isinstance(result, BatchResult)
            # 验证 parse_single 被调用时携带了所有选项
            mock_parse_single.assert_called_once()
            call_kwargs = mock_parse_single.call_args
            assert call_kwargs.kwargs.get("verbose") is True or call_kwargs[1].get("verbose") is True


class TestUnifiedOutputEntrypoint:
    """验证 CLI 单文件走 parse_single 路径。"""

    def test_cli_single_file_uses_parse_single(self):
        """CLI 单文件应调用 parse_single。"""
        from uasset_read.cli import main
        with patch("uasset_read.cli.parse_single") as mock_ps:
            mock_ps.return_value = '{"ok": true}'
            with patch("sys.argv", ["uasset_read", "test.uasset", "--json"]):
                with patch("pathlib.Path.is_file", return_value=True):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    mock_ps.assert_called_once()


# ---------------------------------------------------------------------------
# API 清理与辅助功能测试（来自 test_api_cleanup.py）
# ---------------------------------------------------------------------------


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
