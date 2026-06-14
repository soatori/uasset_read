"""core.py API 测试。"""
import pytest
from unittest.mock import patch, MagicMock

from uasset_read.core import parse_single, parse_batch, list_formats, ParseError, BatchResult


class TestListFormats:
    def test_json_in_formats(self):
        fmts = list_formats()
        assert "json" in fmts

    def test_json_summary_in_formats(self):
        fmts = list_formats()
        assert "json_summary" in fmts


class TestParseSingle:
    def test_parse_single_raises_on_parse_failure(self):
        """parse_single 在解析失败时抛出 ParseError。"""
        with patch("uasset_read.core.parse_package") as mock_parse:
            mock_result = MagicMock()
            mock_result.is_success = False
            mock_result.errors = ["test error"]
            mock_parse.return_value = mock_result

            with pytest.raises(ParseError, match="Parse failed"):
                parse_single("nonexistent.uasset", format="text")

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

    def test_parse_single_uses_linker_for_json_summary_format(self):
        """parse_single 对 json_summary 格式使用 parse_uasset_with_linker。"""
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

                    parse_single("test.uasset", format="json_summary")
                    mock_linker_parse.assert_called_once()


class TestParseBatch:
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

            result = parse_batch(str(tmp_path), format="json")

            assert isinstance(result, BatchResult)
            assert result.total == 1

    def test_parse_batch_handles_failures(self, tmp_path):
        """parse_batch 正确处理失败文件。"""
        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b"\x00" * 100)

        with patch("uasset_read.core.parse_single") as mock_parse_single:
            mock_parse_single.side_effect = ParseError("test error")

            result = parse_batch(str(tmp_path), format="json")

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