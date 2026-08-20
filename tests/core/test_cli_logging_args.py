"""Tests for --log-format CLI argument."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest


def _run_cli_help():
    """Run `python -m uasset_read --help` and return stdout."""
    src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src")
    env = {**os.environ, "PYTHONPATH": src_dir}
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    return result


class TestCLILogFormat:
    """--log-format CLI argument."""

    def test_log_format_argument(self):
        result = _run_cli_help()
        assert "--log-format" in result.stdout

    def test_log_format_choices(self):
        result = _run_cli_help()
        assert "text" in result.stdout
        assert "json" in result.stdout

    def test_log_format_help_text(self):
        result = _run_cli_help()
        assert "Log output format" in result.stdout
