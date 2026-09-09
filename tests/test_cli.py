"""CLI regression tests."""

import sys

import pytest

from uasset_read import cli


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


@pytest.mark.parametrize("flag", ["--include-parent-assets", "--asset-root"])
def test_retired_parent_asset_flags_are_rejected(monkeypatch, flag: str, capsys) -> None:
    """Parent-asset resolution is retired (Gate G); flags exit 2 with a clear message."""
    monkeypatch.setattr(sys, "argv", ["uasset_read", flag])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 2
    assert "parent-asset resolution is retired" in capsys.readouterr().err


@pytest.mark.parametrize(
    "flag",
    ["--clean-logs", "--log-dir", "--log-keep-latest", "--log-max-total-mb"],
)
def test_retired_log_cleanup_flags_are_rejected(monkeypatch, flag: str, capsys) -> None:
    """Gate L: file-log cleanup surface is retired; flags exit 2 with a clear message."""
    monkeypatch.setattr(sys, "argv", ["uasset_read", flag])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "log cleanup / file logging helpers are retired" in err
