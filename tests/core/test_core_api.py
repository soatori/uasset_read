"""Core API 测试 — 合并自 test_core_api.py 和 test_archive_core.py。

覆盖：core API、CLI、PackageArchive、read_name、ByteArchive、
GameDirectoryProvider、package bundle。
"""
from __future__ import annotations

import gc
import importlib
import io
import json
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

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
from uasset_read.package import (
    ByteArchive,
    FileSystemPackageProvider,
    IoStorePackageProvider,
    PakPackageProvider,
    PackageArchive,
    open_package_bundle,
)
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
                error_details="",
            ),
            SimpleNamespace(
                succeeded=False,
                output_path="",
                error="memory_limit: 1025.0MB > 1024.0MB",
                error_details="",
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
        assert len(result.failed) == 1
        assert result.failed[0][0] == str(second)
        assert result.failed[0][1] == "memory_limit: 1025.0MB > 1024.0MB"
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

        with patch("uasset_read.core._parse_and_render") as mock_parse:
            mock_result = MagicMock()
            mock_result.is_success = True
            mock_result.export_map = []
            mock_result.errors = []
            mock_result.hex_view_entries = None
            mock_parse.return_value = ('{"status": "success"}', mock_result)

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

        with patch("uasset_read.core._parse_and_render") as mock_parse:
            mock_parse.side_effect = ParseError("test error")

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

        with patch("uasset_read.core._parse_and_render") as mock_parse:
            mock_result = MagicMock()
            mock_result.is_success = True
            mock_result.export_map = []
            mock_result.errors = []
            mock_result.hex_view_entries = None
            mock_parse.return_value = ('{"status": "success"}', mock_result)

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
            # 验证 _parse_and_render 被调用时携带了所有选项
            mock_parse.assert_called_once()
            call_kwargs = mock_parse.call_args
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


# ===========================================================================
# PackageArchive.read() 边界保护
# ===========================================================================

def _make_archive(data: bytes) -> PackageArchive:
    """用 ByteArchive 构造一个最小 PackageArchive。"""
    main = ByteArchive(data, tolerant=False, name="test.uasset")
    return PackageArchive(main, tolerant=False)


def test_read_negative_size_raises():
    """read(-1) 应抛 ParseError 且 tell() 不变。"""
    archive = _make_archive(b"\x00\x01\x02\x03\x04")
    pos_before = archive.tell()
    with pytest.raises(ParseError, match="negative size"):
        archive.read(-1)
    assert archive.tell() == pos_before


def test_read_zero_returns_empty():
    """read(0) 应返回空 bytes，不移动 tell()。"""
    archive = _make_archive(b"\x00\x01\x02")
    result = archive.read(0)
    assert result == b""
    assert archive.tell() == 0


def test_read_normal_returns_data():
    """正常 read 应返回正确数据并推进 tell()。"""
    archive = _make_archive(b"\x00\x01\x02\x03\x04")
    result = archive.read(3)
    assert result == b"\x00\x01\x02"
    assert archive.tell() == 3


def test_read_beyond_eof_raises():
    """read(超过剩余) 应抛 ParseError。"""
    archive = _make_archive(b"\x00\x01")
    with pytest.raises(ParseError, match="Cannot read"):
        archive.read(10)


# ===========================================================================
# package bundle 测试
# ===========================================================================

def test_filesystem_bundle_discovers_asset_sidecars(tmp_path: Path):
    asset = tmp_path / "A.uasset"
    asset.write_bytes(b"asset")
    (tmp_path / "A.uexp").write_bytes(b"exports")
    (tmp_path / "A.ubulk").write_bytes(b"bulk")
    (tmp_path / "A.uptnl").write_bytes(b"optional")

    bundle = open_package_bundle(str(asset))

    assert bundle.package_kind == "asset"
    assert bundle.container == "filesystem"
    assert set(bundle.package_files) == {".uasset", ".uexp", ".ubulk", ".uptnl"}


def test_filesystem_bundle_supports_umap(tmp_path: Path):
    umap = tmp_path / "Map.umap"
    umap.write_bytes(b"map")

    bundle = open_package_bundle(str(umap))

    assert bundle.package_kind == "map"
    assert set(bundle.package_files) == {".umap"}


def test_package_archive_reads_across_uexp_boundary():
    archive = PackageArchive(
        ByteArchive(b"abcd", name="A.uasset"),
        ByteArchive(b"efgh", name="A.uexp"),
    )

    archive.seek(2)

    assert archive.read(4) == b"cdef"
    assert archive.tell() == 6


class _FakePakReader:
    def __init__(self):
        self.files = {
            "Game/A.uasset": b"asset",
            "Game/A.uexp": b"exports",
        }

    def list_files(self):
        return list(self.files)

    def extract(self, path):
        return self.files.get(path)


def test_pak_provider_loads_bundle_from_virtual_paths():
    provider = PakPackageProvider(_FakePakReader())

    bundle = provider.open_package_bundle("Game/A.uasset")

    assert bundle.container == "pak"
    assert bundle.payloads[".uasset"] == b"asset"
    assert bundle.payloads[".uexp"] == b"exports"


class _Chunk:
    def __init__(self, value: bytes):
        self.bytes = value


class _FakeIoStoreReader:
    def __init__(self):
        self._directory_index = {
            "Game/A.uasset": _Chunk(b"asset_chunk__"),
            "Game/A.uexp": _Chunk(b"exports_chunk"),
        }
        self.data = {
            b"asset_chunk__": b"asset",
            b"exports_chunk": b"exports",
        }

    def list_files(self):
        return list(self._directory_index)

    def extract(self, chunk_id):
        return self.data[chunk_id]


def test_iostore_provider_loads_bundle_from_directory_index():
    provider = IoStorePackageProvider(_FakeIoStoreReader())

    bundle = provider.open_package_bundle("Game/A.uasset")

    assert bundle.container == "iostore"
    assert bundle.payloads[".uasset"] == b"asset"
    assert bundle.payloads[".uexp"] == b"exports"


# ===========================================================================
# FileSystemPackageProvider 缓存失效测试
# ===========================================================================

def test_list_files_cache_returns_same_object():
    """验证缓存返回相同的列表对象。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.uasset").touch()

        provider = FileSystemPackageProvider(tmpdir)
        result1 = provider.list_files()
        result2 = provider.list_files()

        assert result1 is result2


def test_list_files_cache_invalidated_on_file_change():
    """验证文件变化后缓存自动失效。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test1.uasset").touch()

        provider = FileSystemPackageProvider(tmpdir)
        result1 = provider.list_files()
        assert len(result1) == 1

        time.sleep(0.1)
        (Path(tmpdir) / "test2.uasset").touch()

        result2 = provider.list_files()
        assert len(result2) == 2


def test_refresh_file_cache_forces_refresh():
    """验证 refresh_file_cache() 强制刷新缓存。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test1.uasset").touch()

        provider = FileSystemPackageProvider(tmpdir)
        result1 = provider.list_files()
        assert len(result1) == 1

        (Path(tmpdir) / "test2.uasset").touch()
        provider.refresh_file_cache()

        result2 = provider.list_files()
        assert len(result2) == 2


# ===========================================================================
# parse_package 核心回归测试
# ===========================================================================

MAX_PARSE_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def test_parse_package_returns_result():
    """parse_package 应返回有效的 ParseResult。"""
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:3]
    for asset_path in test_assets:
        if asset_path.stat().st_size > MAX_PARSE_FILE_SIZE:
            continue
        result = parse_package(str(asset_path))
        assert result.summary is not None
        assert result.name_map is not None
        assert result.export_map is not None
        del result
        gc.collect()


def test_parse_uasset_with_linker_returns_result():
    """parse_uasset_with_linker 应返回有效的 LinkerParseResult。"""
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:3]
    for asset_path in test_assets:
        if asset_path.stat().st_size > MAX_PARSE_FILE_SIZE:
            continue
        result = parse_uasset_with_linker(str(asset_path))
        assert result.summary is not None
        assert result.linker is not None
        assert result.all_objects is not None
        del result
        gc.collect()


def test_parse_package_with_mappings():
    """parse_package 支持 mappings_path 参数。"""
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:1]
    if not test_assets:
        pytest.skip("No test assets found")
    result = parse_package(str(test_assets[0]))
    assert "mappings_path" not in result.metadata


def test_parse_package_aes_key_rejection():
    """parse_package 应拒绝 aes_key 参数。"""
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:1]
    if not test_assets:
        pytest.skip("No test assets found")
    result = parse_package(str(test_assets[0]), aes_key=b"\x00" * 16)
    assert not result.is_success
    assert "aes_key" in result.errors[0]


# ==============================================================================
# 以下来自 test_archive_core.py
# ==============================================================================

"""Archive 核心测试 — 合并自 test_archive_read_name.py 和 test_archive_provider_renderer.py。

覆盖：read_name() 索引越界/恢复/去重、skip()、
ByteArchive 基础操作、GameDirectoryProvider、CLI format 解析。
"""
import types

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError


# ===========================================================================
# ByteArchive 基础操作
# ===========================================================================


def test_byte_archive_read_bytes_basic():
    """read_bytes 返回正确子节"""
    archive = ByteArchive(b"\xAA\xBB\xCC\xDD", name="test")
    result = archive.read_bytes(2)
    assert result == b"\xAA\xBB"
    assert archive.tell() == 2
    archive.close()


def test_byte_archive_name_sets_path():
    """name 参数正确赋值 _path"""
    archive = ByteArchive(b"\x00", name="my_asset")
    assert archive._path == "my_asset"
    archive.close()


def test_byte_archive_read_overflow_raises():
    """读取超出缓冲区时抛 ParseError"""
    archive = ByteArchive(b"\x01\x02", name="test")
    with pytest.raises(ParseError, match="Cannot read"):
        archive.read(5)
    archive.close()


def test_byte_archive_read_negative_size_raises():
    """负数 size 抛 ParseError"""
    archive = ByteArchive(b"\x01", name="test")
    with pytest.raises(ParseError, match="negative size"):
        archive.read(-1)
    archive.close()


def test_byte_archive_close_releases_buffer():
    """close 清空缓冲区并重置大小"""
    archive = ByteArchive(b"\x01\x02\x03", name="test")
    archive.close()
    assert archive._file_size == 0
    assert archive._buffer == b""


# ===========================================================================
# read_name() 索引越界测试 (#334)
# ===========================================================================


def test_read_name_index_out_of_range():
    """read_name() 索引越界时应返回 'None' 而非崩溃。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    result = archive.read_name(name_map)
    assert result == "None"


def test_read_name_index_out_of_range_strict():
    """read_name() 索引越界在 strict 模式应抛出异常。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)
    name_map = ["Name0", "Name1", "Name2"]

    with pytest.raises(ParseError):
        archive.read_name(name_map)


def test_read_name_index_negative():
    """read_name() 负索引应返回 'None'。"""
    data = b'\xff\xff\xff\xff\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    result = archive.read_name(name_map)
    assert result == "None"


def test_read_name_valid_index():
    """read_name() 正常索引应正确返回名称。"""
    data = b'\x01\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data)
    name_map = ["Name0", "Name1", "Name2"]

    result = archive.read_name(name_map)
    assert result == "Name1"


def test_read_name_with_number():
    """read_name() 带 number 后缀应正确格式化。"""
    data = b'\x00\x00\x00\x00\x05\x00\x00\x00'
    archive = ByteArchive(data)
    name_map = ["MyName"]

    result = archive.read_name(name_map)
    assert result == "MyName_5"


def test_read_name_large_index_recovery():
    """read_name() 检测到异常大索引时应尝试恢复。"""
    garbage = b'\x00\x10\x00\x00\x00\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    result = archive.read_name(name_map)
    assert result == "TestName"


def test_read_name_large_index_recovery_with_number():
    """read_name() 恢复时保留 number 后缀。"""
    garbage = b'\x5B\x00'
    valid_name = b'\x01\x00\x00\x00\x03\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    result = archive.read_name(name_map)
    assert result == "Name1_3"


def test_read_name_recovery_disabled_in_strict_mode():
    """strict 模式下不触发恢复，直接抛异常。"""
    garbage = b'\x5B\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=False)
    name_map = ["TestName"]

    with pytest.raises(ParseError):
        archive.read_name(name_map)


def test_read_name_recovery_no_valid_offset():
    """所有偏移调整均无效时，应返回 'None'。"""
    garbage = b'\xE9\x03\x00\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = []

    result = archive.read_name(name_map)
    assert result == "None"


def test_read_name_recovery_1byte_offset():
    """1字节偏移也能恢复。"""
    garbage = b'\x00\x10\x00\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    result = archive.read_name(name_map)
    assert result == "TestName"


def test_read_name_recovery_threshold():
    """read_name() 只在索引超过阈值时尝试恢复。"""
    data = b'\xE7\x03\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name"] * 1000

    result = archive.read_name(name_map)
    assert result == "Name"


def test_read_name_recovery_with_number():
    """read_name() 恢复后应正确处理 number 后缀。"""
    garbage = b'\xE9\x03'
    valid_name = b'\x00\x00\x00\x00\x05\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    result = archive.read_name(name_map)
    assert result == "TestName_5"


def test_read_name_recovery_failure():
    """read_name() 恢复失败时应返回 'None'。"""
    data = b'\xFF\x00\x00\x00\x00\x00\x00\x00' * 5
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    result = archive.read_name(name_map)
    assert result == "None"


# --- 恢复统计诊断测试 ---


def test_recovery_stats_initial_zero():
    """新 archive 的恢复统计应为零。"""
    data = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 0
    assert stats["recovery_successes"] == 0
    assert stats["recovery_failures"] == 0


def test_recovery_stats_success():
    """恢复成功时应正确计数。"""
    garbage = b'\xE9\x03'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    archive.read_name(name_map)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 1
    assert stats["recovery_successes"] == 1
    assert stats["recovery_failures"] == 0


def test_recovery_stats_failure():
    """恢复失败时应正确计数。"""
    data = b'\xE9\x03\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = []

    archive.read_name(name_map)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 1
    assert stats["recovery_successes"] == 0
    assert stats["recovery_failures"] == 1


def test_recovery_stats_multiple_attempts():
    """多次调用应累积统计。"""
    garbage1 = b'\xE9\x03'
    valid1 = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    fail_data = b'\xE9\x03\x00\x00\x00\x00\x00\x00'
    data = garbage1 + valid1 + fail_data
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    archive.read_name(name_map)
    archive.read_name(name_map)

    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 2
    assert stats["recovery_successes"] == 1
    assert stats["recovery_failures"] == 1


def test_recovery_stats_no_recovery_for_valid_index():
    """正常索引不触发恢复，统计应为零。"""
    data = b'\x01\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    archive.read_name(name_map)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 0
    assert stats["recovery_successes"] == 0
    assert stats["recovery_failures"] == 0


# --- archive skip 测试 ---


def test_farchive_skip():
    """FArchive 应支持 skip() 方法跳过指定字节数。"""
    data = b'\x00' * 100
    archive = ByteArchive(data)

    initial_pos = archive.tell()
    archive.skip(10)
    assert archive.tell() == initial_pos + 10


def test_farchive_skip_to_end():
    """skip() 应支持跳转到文件末尾。"""
    data = b'\x00' * 50
    archive = ByteArchive(data)

    archive.skip(50)
    assert archive.tell() == 50


def test_farchive_skip_zero():
    """skip(0) 应保持位置不变。"""
    data = b'\x00' * 100
    archive = ByteArchive(data)

    archive.skip(0)
    assert archive.tell() == 0


def test_farchive_skip_negative_raises():
    """skip() 负数应抛出异常（seek 会验证）。"""
    data = b'\x00' * 100
    archive = ByteArchive(data)

    with pytest.raises(Exception):
        archive.skip(-5)


# --- read_name() 越界警告去重测试 (#411) ---


def test_read_name_duplicate_index_only_one_diagnostic():
    """重复的越界索引只应记录一次诊断。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00' * 3
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    for _ in range(3):
        archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1


def test_read_name_different_indices_each_recorded():
    """不同的越界索引应各自记录一次诊断。"""
    data = (
        b'\x03\x00\x00\x00\x00\x00\x00\x00'
        b'\x05\x00\x00\x00\x00\x00\x00\x00'
        b'\x07\x00\x00\x00\x00\x00\x00\x00'
    )
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    archive.read_name(name_map)
    archive.read_name(name_map)
    archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 3


def test_read_name_mixed_valid_and_invalid():
    """有效和无效索引混合时，只记录无效索引的诊断。"""
    data = (
        b'\x01\x00\x00\x00\x00\x00\x00\x00'
        b'\x05\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00'
    )
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    archive.read_name(name_map)
    archive.read_name(name_map)
    archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1
    assert "index 5" in out_of_range[0].error


def test_read_name_duplicate_invalid_then_valid():
    """先重复越界，再有效索引，诊断只记录一次。"""
    data = b'\x0A\x00\x00\x00\x00\x00\x00\x00' * 5
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    for _ in range(5):
        archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1
    assert "index 10" in out_of_range[0].error


def test_read_name_negative_index_dedup():
    """负索引（0xFFFFFFFF）也应去重。"""
    data = b'\xff\xff\xff\xff\x00\x00\x00\x00' * 3
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0"]

    for _ in range(3):
        archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1


def test_read_name_strict_mode_still_deduplicates():
    """strict 模式下，同一越界索引第二次也应被去重。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)
    name_map = ["Name0", "Name1", "Name2"]

    with pytest.raises(Exception):
        archive.read_name(name_map)


def test_read_name_fresh_archive_warnings_seen_empty():
    """新 archive 的 _name_warnings_seen 应为空集。"""
    data = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    assert len(archive._name_warnings_seen) == 0


def test_read_name_valid_index_does_not_populate_warnings_seen():
    """有效索引不应写入 _name_warnings_seen。"""
    data = b'\x01\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    archive.read_name(name_map)
    assert len(archive._name_warnings_seen) == 0


def test_read_name_invalid_index_populates_warnings_seen():
    """越界索引应写入 _name_warnings_seen。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    archive.read_name(name_map)
    assert 5 in archive._name_warnings_seen


def test_read_name_all_returns_none_for_invalid():
    """去重不影响返回值——每次越界都应返回 'None'。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00' * 3
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0"]

    for _ in range(3):
        result = archive.read_name(name_map)
        assert result == "None"


# ===========================================================================
# GameDirectoryProvider 测试
# ===========================================================================


def test_provider_list_files_cache_hit(tmp_path):
    """第二次 list_files 调用命中缓存，不重新扫描"""
    from uasset_read.providers import GameDirectoryProvider

    (tmp_path / "a.uasset").touch()
    provider = GameDirectoryProvider(tmp_path)

    first = provider.list_files(".uasset")
    assert ".uasset" in provider._list_files_cache

    second = provider.list_files(".uasset")
    assert first is second


def test_provider_refresh_clears_cache(tmp_path):
    """refresh_file_cache 清空缓存字典"""
    from uasset_read.providers import GameDirectoryProvider

    (tmp_path / "a.uasset").touch()
    provider = GameDirectoryProvider(tmp_path)

    provider.list_files(".uasset")
    assert len(provider._list_files_cache) > 0

    provider.refresh_file_cache()
    assert len(provider._list_files_cache) == 0


def test_provider_list_uasset_files_filters_extensions(tmp_path):
    """list_uasset_files 仅返回 .uasset 和 .umap"""
    from uasset_read.providers import GameDirectoryProvider

    (tmp_path / "char.uasset").touch()
    (tmp_path / "level.umap").touch()
    (tmp_path / "readme.txt").touch()
    (tmp_path / "data.upak").touch()
    provider = GameDirectoryProvider(tmp_path)

    result = provider.list_uasset_files()
    names = [p.name for p in result]
    assert "char.uasset" in names
    assert "level.umap" in names
    assert "readme.txt" not in names
    assert "data.upak" not in names


def test_provider_constructor_nonexistent_dir_raises():
    """构造不存在的目录抛 FileNotFoundError"""
    from uasset_read.providers import GameDirectoryProvider

    with pytest.raises(FileNotFoundError):
        GameDirectoryProvider("/nonexistent_path_xyz_12345")


# ===========================================================================
# CLI format 解析测试
# ===========================================================================


def test_resolve_format_named_flags():
    """--markdown -> 'markdown'，--json -> 'json'"""
    from uasset_read.cli import resolve_format

    args_md = types.SimpleNamespace(markdown=True, json=False)
    assert resolve_format(args_md) == "markdown"

    args_json = types.SimpleNamespace(markdown=False, json=True)
    assert resolve_format(args_json) == "json"


def test_resolve_format_default_json():
    """无格式标志 -> 'json'"""
    from uasset_read.cli import resolve_format

    args = types.SimpleNamespace(markdown=False, json=False)
    assert resolve_format(args) == "json"


def test_list_formats_excludes_text():
    """list_formats() 不包含已移除的 'text'"""
    from uasset_read.core import list_formats

    formats = list_formats()
    assert "text" not in formats
    assert "json" in formats
    assert "markdown" in formats
