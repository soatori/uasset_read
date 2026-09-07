"""CLI regression tests."""

import sys

import pytest

from uasset_read import cli


def test_clean_logs_uses_surviving_log_config_fields(monkeypatch, capsys) -> None:
    """`--clean-logs` must not crash after the log-config inlining (#587)."""
    monkeypatch.setattr(sys, "argv", ["uasset_read", "--clean-logs"])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 0
    assert "Would delete" in capsys.readouterr().out
