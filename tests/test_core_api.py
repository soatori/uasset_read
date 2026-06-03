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