"""CLI 输出格式测试 — 合并自 test_cli_output.py、test_core_api.py CLI 部分。

覆盖：批量输出 partial 统计、格式解析、CLI 错误路径、--log-level off 回归。
"""
import json
import subprocess
import sys
import types
from pathlib import Path

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


# ============================================================================
# 1. 批量输出 partial 统计
# ============================================================================

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


# ============================================================================
# 2. partial 为空时不输出
# ============================================================================

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


# ============================================================================
# 3. CLI 格式解析
# ============================================================================

def test_resolve_format_named_flags():
    """--markdown -> 'markdown'，--json -> 'json'。"""
    from uasset_read.cli import resolve_format

    args_md = types.SimpleNamespace(markdown=True, json=False)
    assert resolve_format(args_md) == "markdown"

    args_json = types.SimpleNamespace(markdown=False, json=True)
    assert resolve_format(args_json) == "json"


# ============================================================================
# 4. CLI 非目录输入错误路径
# ============================================================================

def test_parse_batch_raises_on_non_directory():
    """parse_batch 在非目录输入时抛出 ValueError。"""
    from uasset_read.core import parse_batch

    with pytest.raises(ValueError, match="Not a directory"):
        parse_batch("nonexistent_directory")


# ============================================================================
# 5. --log-level off CLI 回归
# ============================================================================

def test_cli_log_level_off(tmp_path):
    """--log-level off 应正常输出 JSON 而非崩溃。"""
    sample = Path(__file__).parent / "samples" / "FirstPerson_BP_FirstPersonCharacter.uasset"
    if not sample.exists():
        pytest.skip("测试样本不存在")

    result = subprocess.run(
        [sys.executable, "run.py", str(sample), "--json", "--log-level", "off"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        timeout=30,
    )
    assert result.returncode == 0, f"exit={result.returncode}\nstderr={result.stderr}"
    assert "Project logging is disabled" not in result.stderr
    # stdout 应为可解析 JSON
    json.loads(result.stdout)
