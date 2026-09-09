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


@pytest.mark.parametrize(
    "flag",
    [
        "--log-level",
        "--log-cleanup",
        "--no-log-cleanup",
        "--log-max-bytes",
        "--log-backup-count",
        "--log-format",
    ],
)
def test_retired_log_flags_are_rejected(monkeypatch, flag: str) -> None:
    """Dead log flags were parsed but never read; main() maps unknown flags to exit 3."""
    monkeypatch.setattr(sys, "argv", ["uasset_read", flag])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 3
