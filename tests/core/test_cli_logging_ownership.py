import sys

import pytest

from uasset_read import cli
from uasset_read.config import LogConfig


def test_cli_builds_enabled_debug_log_config_by_default(tmp_path):
    args = cli.create_parser().parse_args([
        str(tmp_path / "asset.uasset"),
        "--log-dir",
        str(tmp_path / "logs"),
    ])

    config = cli._log_config_from_args(args)

    assert config.level == "debug"
    assert config.enabled is True
    assert config.dir == str(tmp_path / "logs")
    assert config.repeat_limit == 5
    assert config.auto_cleanup is True
    assert config.keep_latest == 20
    assert config.max_total_bytes == 500 * 1024 * 1024


def test_cli_log_level_off_disables_file_logging(tmp_path):
    args = cli.create_parser().parse_args([
        str(tmp_path / "asset.uasset"),
        "--log-level",
        "off",
    ])

    config = cli._log_config_from_args(args)

    assert config.level == "off"
    assert config.enabled is False


def test_cli_can_disable_cleanup_and_debug_aggregation(tmp_path):
    args = cli.create_parser().parse_args([
        str(tmp_path / "asset.uasset"),
        "--no-log-cleanup",
        "--log-repeat-limit",
        "0",
    ])

    config = cli._log_config_from_args(args)

    assert config.auto_cleanup is False
    assert config.repeat_limit == 0


def test_python_log_config_does_not_auto_cleanup_by_default():
    config = LogConfig()

    assert config.auto_cleanup is False
    assert config.repeat_limit == 5


def test_cli_help_describes_run_cleanup_and_safe_dry_run():
    help_text = cli.create_parser().format_help()
    normalized = " ".join(help_text.split())

    assert "newest N complete runs" in normalized
    assert "Dry-run log cleanup plan" in normalized
    assert "pass --log-cleanup to delete" not in normalized


def test_cli_single_parse_passes_structured_log_config(monkeypatch, tmp_path):
    asset_path = tmp_path / "asset.uasset"
    asset_path.write_bytes(b"")
    captured = {}

    def fake_parse_single(*args, **kwargs):
        captured.update(kwargs)
        return "{}"

    monkeypatch.setattr(cli, "parse_single", fake_parse_single)
    monkeypatch.setattr(sys, "argv", ["uasset_read", str(asset_path)])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0
    assert isinstance(captured["log_config"], LogConfig)
    assert captured["log_config"].enabled is True
    assert "log_level" not in captured
    assert "log_dir" not in captured
