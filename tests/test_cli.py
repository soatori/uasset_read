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
        "--include-parent-assets",
        "--asset-root",
        "--clean-logs",
        "--log-dir",
        "--log-keep-latest",
        "--log-max-total-mb",
        "--legacy-json",
        "--markdown",
        "--list-formats",
        "--diff",
    ],
)
def test_unknown_flags_are_rejected(monkeypatch, flag: str) -> None:
    """Removed flags fall through to argparse; main() maps unknown flags to exit 3."""
    monkeypatch.setattr(sys, "argv", ["uasset_read", flag])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 3
