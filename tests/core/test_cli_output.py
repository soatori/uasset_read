"""CLI 输出格式测试。"""
import pytest
from unittest.mock import patch, MagicMock


def _make_args(tmp_path):
    """构造 _handle_batch 所需的最小 args 对象。"""
    return type("Args", (), {
        "file": str(tmp_path),
        "batch_dir": str(tmp_path / "output"),
        "strict": False,
        "verbose": False,
        "schema": False,
        "function_graphs": False,
        "include_parent_assets": False,
        "asset_root": None,
        "mappings": None,
        "game": None,
        "full_parse": False,
    })()


def _run_handle_batch(args, result):
    """执行 _handle_batch 并捕获 SystemExit。"""
    from uasset_read.cli import _handle_batch
    with patch("uasset_read.cli.parse_batch", return_value=result), \
         patch("uasset_read.cli.resolve_format", return_value="json"), \
         patch("uasset_read.cli._log_config_from_args", return_value=MagicMock()):
        with pytest.raises(SystemExit):
            _handle_batch(args)


def test_batch_output_includes_partial_statistics(tmp_path, capsys):
    """批量导出 CLI 输出应包含 partial 统计信息。"""
    from uasset_read.core import BatchResult

    result = BatchResult()
    result.total = 10
    result.success = ["file1.uasset", "file2.uasset"]
    result.skipped = []
    result.failed = []
    result.partial = ["file3.uasset", "file4.uasset", "file5.uasset"]
    result.partial_reasons = {
        "opaque": ["file3.uasset"],
        "partial_metadata": ["file4.uasset", "file5.uasset"],
    }

    _run_handle_batch(_make_args(tmp_path), result)
    captured = capsys.readouterr()
    assert "Partial: 3" in captured.err
    assert "Opaque: 1" in captured.err
    assert "Partial Metadata: 2" in captured.err


def test_batch_output_no_partial_when_empty(tmp_path, capsys):
    """partial 为空时不应输出 Partial 行。"""
    from uasset_read.core import BatchResult

    result = BatchResult()
    result.total = 2
    result.success = ["file1.uasset", "file2.uasset"]
    result.skipped = []
    result.failed = []
    result.partial = []
    result.partial_reasons = {}

    _run_handle_batch(_make_args(tmp_path), result)
    captured = capsys.readouterr()
    assert "Partial" not in captured.err
