"""Miscellaneous infrastructure tests — CLI format, batch output, logging, entry point integrity."""
from __future__ import annotations

import inspect
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from uasset_read.cli import resolve_format, _handle_batch
from uasset_read.core import parse_batch, BatchResult
from uasset_read.project_logging import project_logging_session, current_log_run_id


# ---------------------------------------------------------------------------
# CLI format resolution
# ---------------------------------------------------------------------------

def test_resolve_format_coverage():
    """resolve_format returns correct format for all flags."""
    # markdown flag
    args_md = types.SimpleNamespace(markdown=True, json=False)
    assert resolve_format(args_md) == "markdown"

    # json flag
    args_json = types.SimpleNamespace(markdown=False, json=True)
    assert resolve_format(args_json) == "json"

    # default (no flag)
    args_default = types.SimpleNamespace(markdown=False, json=False)
    assert resolve_format(args_default) == "json"


# ---------------------------------------------------------------------------
# Batch output and _handle_batch integration
# ---------------------------------------------------------------------------

def _make_args(tmp_path):
    """Minimal args object for _handle_batch."""
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
        "output_level": "standard",
    })()


def _run_handle_batch(args, result):
    """Execute _handle_batch and capture SystemExit."""
    with patch("uasset_read.cli.parse_batch", return_value=result), \
         patch("uasset_read.cli.resolve_format", return_value="json"), \
         patch("uasset_read.cli._log_config_from_args", return_value=MagicMock()):
        with pytest.raises(SystemExit):
            _handle_batch(args)


def test_batch_output_statistics(tmp_path, capsys):
    """_handle_batch prints partial statistics when partial list is non-empty."""
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


# ---------------------------------------------------------------------------
# project_logging session behavior
# ---------------------------------------------------------------------------

def test_disabled_session_no_run_id():
    """Disabled session has run_id=None and supports context manager."""
    session = project_logging_session(enabled=False, level="off")
    assert current_log_run_id() is None
    session.close()
    with project_logging_session(enabled=False, level="off") as s:
        assert s is not None and current_log_run_id() is None


# ---------------------------------------------------------------------------
# Core API parameter completeness
# ---------------------------------------------------------------------------

def test_parse_batch_has_required_params():
    """parse_batch exposes output_level and hex_view parameters."""
    sig = inspect.signature(parse_batch)
    assert "output_level" in sig.parameters, (
        f"parse_batch missing output_level; current: {list(sig.parameters.keys())}"
    )
    assert "hex_view" in sig.parameters, (
        f"parse_batch missing hex_view"
    )
