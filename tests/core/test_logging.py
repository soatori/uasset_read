"""日志系统综合测试 — 合并自 logging_config, logging_ownership, cli_logging_args,
cli_logging_ownership, project_logging, project_logging_session。

覆盖：日志级别配置、handler 拥有权、CLI 参数解析、project logging 集成、
session 状态管理、cleanup、轮转、debug 聚合。
"""

import importlib
import io
import logging
import logging.handlers
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import uasset_read
from uasset_read import cli, core
from uasset_read.config import LogConfig
from uasset_read.core import _configure_logging
from uasset_read import project_logging
from uasset_read.project_logging import (
    _build_log_path,
    _reset_logging_state_for_tests,
    configure_project_logging,
    setup_logging,
)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_project_logging():
    _reset_logging_state_for_tests()
    yield
    _reset_logging_state_for_tests()


def _owned_handlers():
    return [
        handler
        for handler in logging.getLogger("uasset_read").handlers
        if getattr(handler, "_uasset_read_project_log_handler", False)
    ]


def _run_cli_help():
    """运行 `python -m uasset_read --help` 并返回 stdout。"""
    src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src")
    env = {**os.environ, "PYTHONPATH": src_dir}
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    return result


def project_logging_config(**kwargs):
    return LogConfig(**kwargs)


# ===========================================================================
# 1. 日志级别规范 (#342)
# ===========================================================================

class TestLoggingLevelSpec:
    """#342: 日志级别规范测试。"""

    def test_logger_has_expected_handlers(self):
        """验证项目 logger 有正确的 handler 配置。"""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(
                log_dir=Path(tmp),
                level="DEBUG",
            )
            logger = logging.getLogger("uasset_read")
            assert len(logger.handlers) > 0
            _reset_logging_state_for_tests()

    def test_log_level_can_be_configured(self):
        """验证日志级别可通过参数配置。"""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(
                log_dir=Path(tmp),
                level="WARNING",
            )
            logger = logging.getLogger("uasset_read")
            assert logger.level <= logging.WARNING
            _reset_logging_state_for_tests()


# ===========================================================================
# 2. Handler 拥有权
# ===========================================================================

def test_core_logging_default_does_not_install_file_handler():
    assert _configure_logging() is None
    assert _owned_handlers() == []


def test_core_logging_explicit_config_installs_file_handler(tmp_path):
    path = _configure_logging(
        log_config=LogConfig(dir=str(tmp_path), run_id="explicit"),
    )

    assert path is not None
    assert path.parent == tmp_path.resolve()
    assert len(_owned_handlers()) == 1


def test_parse_single_explicit_log_config_is_scoped_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        core,
        "parse_uasset_with_linker",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parse failed")),
    )

    with pytest.raises(RuntimeError, match="parse failed"):
        core.parse_single(
            "missing.uasset",
            log_config=LogConfig(dir=str(tmp_path), run_id="scoped-error"),
        )

    assert _owned_handlers() == []
    assert len(list(tmp_path.glob("uasset_read-*-scoped-error.log"))) == 1


@pytest.mark.parametrize("entrypoint", ["parse_package", "parse_uasset_with_linker"])
def test_low_level_parse_defaults_do_not_configure_file_logging(monkeypatch, entrypoint):
    parse_module = importlib.import_module("uasset_read.parse_uasset")
    monkeypatch.setattr(parse_module, "_parse_package_core", lambda *args, **kwargs: None)

    getattr(parse_module, entrypoint)("missing.uasset")

    assert _owned_handlers() == []


@pytest.mark.parametrize("entrypoint", ["parse_package", "parse_uasset_with_linker"])
def test_low_level_explicit_log_config_is_scoped(monkeypatch, tmp_path, entrypoint):
    parse_module = importlib.import_module("uasset_read.parse_uasset")
    monkeypatch.setattr(parse_module, "_parse_package_core", lambda *args, **kwargs: None)

    getattr(parse_module, entrypoint)(
        "missing.uasset",
        log_config=LogConfig(dir=str(tmp_path), run_id=f"low-{entrypoint}"),
    )

    assert _owned_handlers() == []
    assert len(list(tmp_path.glob(f"uasset_read-*-low-{entrypoint}.log"))) == 1


def test_public_package_exports_logging_session_api():
    assert uasset_read.ProjectLogSession is not None
    assert callable(uasset_read.project_logging_session)
    assert callable(uasset_read.shutdown_project_logging)


def test_batch_summary_reports_result_counts(caplog):
    result = core.BatchResult(
        total=4,
        success=["one"],
        skipped=[("two", "skip")],
        failed=[("three", "fail"), ("four", "fail")],
    )
    caplog.set_level(logging.INFO, logger="uasset_read.core")

    core._log_batch_summary(result)

    assert "batch_summary total=4 success=1 skipped=1 failed=2" in caplog.text


# ===========================================================================
# 3. CLI 日志参数
# ===========================================================================

class TestCLILoggingArgs:
    """验证日志 CLI 参数正确传递。"""

    def test_log_max_total_mb_argument(self):
        """--log-max-total-mb 参数应被接受。"""
        result = _run_cli_help()
        assert "--log-max-total-mb" in result.stdout

    def test_log_keep_latest_argument(self):
        """--log-keep-latest 参数应被接受。"""
        result = _run_cli_help()
        assert "--log-keep-latest" in result.stdout

    def test_log_max_total_mb_help_text(self):
        """--log-max-total-mb 帮助文本应包含描述。"""
        result = _run_cli_help()
        assert "cap total log storage" in result.stdout

    def test_log_keep_latest_help_text(self):
        """--log-keep-latest 帮助文本应包含描述。"""
        result = _run_cli_help()
        assert "keep only the newest" in result.stdout


# ===========================================================================
# 4. CLI 日志配置
# ===========================================================================

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


def test_clean_logs_dry_run_uses_cli_retention_defaults(monkeypatch, tmp_path):
    args = cli.create_parser().parse_args([
        "--clean-logs",
        "--log-dir",
        str(tmp_path),
    ])
    captured = {}

    def fake_cleanup(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(cli, "cleanup_project_logs", fake_cleanup)

    with pytest.raises(SystemExit) as exc_info:
        cli._handle_clean_logs(args)

    assert exc_info.value.code == 0
    assert captured["keep_latest"] == 20
    assert captured["max_total_bytes"] == 500 * 1024 * 1024
    assert captured["dry_run"] is True


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


# ===========================================================================
# 5. Project logging 集成
# ===========================================================================

class TestLoggingIntegration:
    """端到端日志系统测试。"""

    def test_full_logging_workflow(self, tmp_path):
        """完整的日志工作流：配置 -> 写入 -> 轮转 -> 清理。"""
        _reset_logging_state_for_tests()

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        # 创建多个旧日志文件
        for i in range(10):
            old_log = log_dir / f"uasset_read-2025010{i}-000000-pid1234-test{i}.log"
            old_log.write_text(f"old log content {i}")

        # 配置日志，启用自动清理
        _log_path = configure_project_logging(
            project_root=tmp_path,
            log_dir=log_dir,
            max_bytes=1024,  # 1KB 触发轮转
            backup_count=2,
            cleanup=True,
            keep_latest=3,
        )

        # 验证旧日志被清理（保留最新 3 个 + 新日志）
        log_files = list(log_dir.glob("uasset_read-*.log*"))
        assert len(log_files) <= 4  # 3 个旧日志 + 1 个新日志

        # 写入足够多的日志触发轮转
        logger = logging.getLogger("uasset_read")
        for _ in range(100):
            logger.info("test message " * 50)

        # 验证轮转发生
        log_files = list(log_dir.glob("uasset_read-*.log*"))
        assert len(log_files) >= 2  # 至少有主日志 + 1 个备份

        _reset_logging_state_for_tests()

    def test_log_level_override(self, tmp_path):
        """验证日志级别正确传递。"""
        _reset_logging_state_for_tests()

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        configure_project_logging(
            project_root=tmp_path,
            log_dir=log_dir,
            level="WARNING",
        )

        logger = logging.getLogger("uasset_read")
        handler = logger.handlers[0]
        assert handler.level == logging.WARNING

        _reset_logging_state_for_tests()

    def test_cleanup_project_logs_function(self, tmp_path):
        """验证 cleanup_project_logs 函数工作正常。"""
        from uasset_read.project_logging import cleanup_project_logs

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        # 创建不同时间的日志文件
        for i in range(5):
            log_file = log_dir / f"uasset_read-2025010{i}-000000-pid1234-test{i}.log"
            log_file.write_text(f"log content {i}")
            mtime = datetime.now() - timedelta(days=i)
            os.utime(log_file, (mtime.timestamp(), mtime.timestamp()))

        # 测试 keep_latest
        planned = cleanup_project_logs(
            log_dir=log_dir,
            keep_latest=2,
            dry_run=True,
        )
        assert len(planned) == 3  # 应该保留最新 2 个

        # 测试 older_than_days
        planned = cleanup_project_logs(
            log_dir=log_dir,
            older_than_days=2,
            dry_run=True,
        )
        assert len(planned) >= 2  # 应该删除超过 2 天的文件

    def test_cleanup_dry_run_no_deletion(self, tmp_path):
        """验证 dry_run 模式不会删除任何文件。"""
        from uasset_read.project_logging import cleanup_project_logs

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        for i in range(3):
            log_file = log_dir / f"uasset_read-2025010{i}-000000-pid1234-test{i}.log"
            log_file.write_text(f"log content {i}")

        planned = cleanup_project_logs(
            log_dir=log_dir,
            keep_latest=0,  # 标记全部删除
            dry_run=True,
        )
        assert len(planned) == 2

        # 文件应仍然存在
        remaining = list(log_dir.glob("uasset_read-*.log*"))
        assert len(remaining) == 3

    def test_cleanup_real_deletion(self, tmp_path):
        """验证 dry_run=False 确实删除文件。"""
        from uasset_read.project_logging import cleanup_project_logs

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        for i in range(3):
            log_file = log_dir / f"uasset_read-2025010{i}-000000-pid1234-test{i}.log"
            log_file.write_text(f"log content {i}")

        cleanup_project_logs(
            log_dir=log_dir,
            keep_latest=1,  # 只保留最新 1 个
            dry_run=False,
        )

        remaining = list(log_dir.glob("uasset_read-*.log*"))
        assert len(remaining) == 1

    def test_cleanup_nonexistent_dir(self, tmp_path):
        """验证清理不存在的目录不会报错。"""
        from uasset_read.project_logging import cleanup_project_logs

        result = cleanup_project_logs(
            log_dir=tmp_path / "nonexistent",
            keep_latest=1,
            dry_run=True,
        )
        assert result == []

    def test_cleanup_keeps_or_deletes_complete_run_families(self, tmp_path):
        from uasset_read.project_logging import cleanup_project_logs

        log_dir = tmp_path / "log"
        log_dir.mkdir()
        old_base = log_dir / "uasset_read-20260101-000000-000000-pid1-old.log"
        old_backup = log_dir / f"{old_base.name}.1"
        new_base = log_dir / "uasset_read-20260102-000000-000000-pid1-new.log"
        old_base.write_text("old")
        old_backup.write_text("old backup")
        new_base.write_text("new")
        old_time = (datetime.now() - timedelta(days=2)).timestamp()
        new_time = (datetime.now() - timedelta(days=1)).timestamp()
        os.utime(old_base, (old_time, old_time))
        newest_time = datetime.now().timestamp()
        os.utime(old_backup, (newest_time, newest_time))
        os.utime(new_base, (new_time, new_time))

        planned = cleanup_project_logs(
            log_dir=log_dir,
            keep_latest=1,
            dry_run=True,
        )

        assert set(planned) == {new_base}

    def test_cleanup_never_selects_active_run_family(self, tmp_path):
        from uasset_read.project_logging import cleanup_project_logs

        log_dir = tmp_path / "log"
        active = configure_project_logging(log_dir=log_dir, run_id="active")
        try:
            planned = cleanup_project_logs(
                log_dir=log_dir,
                keep_latest=0,
                max_total_bytes=0,
                dry_run=True,
            )
            assert active not in planned
        finally:
            _reset_logging_state_for_tests()


# ===========================================================================
# 6. Project logging session
# ===========================================================================

def test_project_logging_keeps_host_propagation_and_restores_logger_state(tmp_path):
    package_logger = logging.getLogger("uasset_read")
    original_level = logging.WARNING
    package_logger.setLevel(original_level)
    package_logger.propagate = True

    stream = io.StringIO()
    host_handler = logging.StreamHandler(stream)
    root_logger = logging.getLogger()
    root_logger.addHandler(host_handler)
    try:
        configure_project_logging(log_dir=tmp_path, level="DEBUG", run_id="host-test")
        logging.getLogger("uasset_read.session_test").warning("visible to host")
        project_logging.shutdown_project_logging()
    finally:
        root_logger.removeHandler(host_handler)
        host_handler.close()

    assert "visible to host" in stream.getvalue()
    assert package_logger.level == original_level
    assert package_logger.propagate is True
    assert not package_logger.handlers


def test_different_configuration_replaces_owned_handler(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first_path = configure_project_logging(
        log_dir=first_dir,
        level="ERROR",
        run_id="first-run",
    )
    second_path = configure_project_logging(
        log_dir=second_dir,
        level="DEBUG",
        run_id="second-run",
    )

    assert first_path != second_path
    assert second_path is not None
    assert second_path.parent == second_dir.resolve()
    owned_handlers = [
        handler
        for handler in logging.getLogger("uasset_read").handlers
        if getattr(handler, "_uasset_read_project_log_handler", False)
    ]
    assert len(owned_handlers) == 1
    assert owned_handlers[0].level == logging.DEBUG


def test_run_id_identifies_a_unique_run_file(tmp_path):
    first_path = configure_project_logging(log_dir=tmp_path, run_id="first")
    project_logging.shutdown_project_logging()
    second_path = configure_project_logging(log_dir=tmp_path, run_id="second")

    assert first_path is not None
    assert second_path is not None
    assert first_path != second_path
    assert "first" in first_path.name
    assert "second" in second_path.name
    assert first_path.exists()
    assert second_path.exists()


def test_same_configuration_is_idempotent(tmp_path):
    first_path = configure_project_logging(log_dir=tmp_path, run_id="same")
    second_path = configure_project_logging(log_dir=tmp_path, run_id="same")

    assert second_path == first_path
    owned_handlers = [
        handler
        for handler in logging.getLogger("uasset_read").handlers
        if getattr(handler, "_uasset_read_project_log_handler", False)
    ]
    assert len(owned_handlers) == 1


def test_project_logging_session_closes_owned_handler(tmp_path):
    log_path = None
    with project_logging.project_logging_session(
        log_dir=tmp_path,
        run_id="scoped",
    ) as session:
        log_path = session.log_path
        assert session.log_path.exists()
        assert session.run_id == "scoped"
        logging.getLogger("uasset_read.session_test").info("inside scope")

    owned_handlers = [
        handler
        for handler in logging.getLogger("uasset_read").handlers
        if getattr(handler, "_uasset_read_project_log_handler", False)
    ]
    assert owned_handlers == []
    output = log_path.read_text(encoding="utf-8")
    assert "session_start" in output
    assert "session_end" in output
    assert "duration_ms=" in output


def test_session_auto_cleanup_runs_after_close_and_preserves_current_run(tmp_path):
    old_one = tmp_path / "uasset_read-20260101-000000-000000-pid1-old1.log"
    old_two = tmp_path / "uasset_read-20260102-000000-000000-pid1-old2.log"
    old_one.write_text("old one")
    old_two.write_text("old two")

    with project_logging.project_logging_session(
        log_dir=tmp_path,
        run_id="current",
        cleanup_on_close=True,
        keep_latest=1,
        max_total_bytes=0,
    ) as session:
        current_path = session.log_path

    assert current_path.exists()
    assert list(tmp_path.glob("uasset_read-*.log")) == [current_path]


def test_nested_scoped_session_is_rejected_without_replacing_outer_handler(tmp_path):
    with project_logging.project_logging_session(
        log_dir=tmp_path / "outer",
        run_id="outer",
    ) as outer:
        with pytest.raises(RuntimeError, match="already active"):
            project_logging.project_logging_session(
                log_dir=tmp_path / "inner",
                run_id="inner",
            )
        logging.getLogger("uasset_read.session_test").warning("outer remains active")

    output = outer.log_path.read_text(encoding="utf-8")
    assert "outer remains active" in output
    assert not (tmp_path / "inner").exists()


def test_log_context_adds_run_process_asset_and_stage(tmp_path):
    path = configure_project_logging(
        log_dir=tmp_path,
        run_id="context-run",
    )
    assert path is not None

    with project_logging.log_context(asset="Asset.uasset", stage="parse"):
        logging.getLogger("uasset_read.session_test").warning("context detail")
    project_logging.shutdown_project_logging()

    output = path.read_text(encoding="utf-8")
    assert "run=context-run" in output
    assert "pid=" in output
    assert "asset=Asset.uasset" in output
    assert "stage=parse" in output


def test_repeated_debug_templates_are_summarized_without_suppressing_warnings(tmp_path):
    path = configure_project_logging(
        log_dir=tmp_path,
        run_id="repeat-run",
        repeat_limit=2,
    )
    assert path is not None
    logger = logging.getLogger("uasset_read.repeat_test")

    for index in range(5):
        logger.debug("repeated value %d", index)
    for index in range(3):
        logger.warning("warning value %d", index)
    project_logging.shutdown_project_logging()

    output = path.read_text(encoding="utf-8")
    assert output.count("repeated value") == 3
    assert "suppressed=3" in output
    assert output.count("warning value") == 3


def test_scoped_api_logs_asset_lifecycle_and_failure_status(tmp_path):
    @project_logging.scoped_project_logging
    def failing_api(path: str, *, log_config=None):
        raise ValueError("broken")

    with pytest.raises(ValueError, match="broken"):
        failing_api(
            "Asset.uasset",
            log_config=project_logging_config(
                dir=str(tmp_path),
                run_id="lifecycle",
            ),
        )

    path = next(tmp_path.glob("uasset_read-*-lifecycle.log"))
    output = path.read_text(encoding="utf-8")
    assert "asset_start" in output
    assert "asset_end status=error" in output
    assert "duration_ms=" in output


# ===========================================================================
# 7. 日志文件优化（合并自 test_log_file_optimization）
# ===========================================================================

class TestLogFileOptimization:
    def test_run_filename_contains_run_id(self):
        path = _build_log_path(Path(tempfile.mkdtemp()), "test-run")
        basename = os.path.basename(path)
        assert basename.startswith("uasset_read-")
        assert basename.endswith("-test-run.log")

    def test_rotating_handler_used(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            root_logger = logging.getLogger("uasset_read")
            rotating = [h for h in root_logger.handlers
                        if isinstance(h, logging.handlers.RotatingFileHandler)]
            assert len(rotating) >= 1
            _reset_logging_state_for_tests()

    def test_rotation_configured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            root_logger = logging.getLogger("uasset_read")
            rotating = [h for h in root_logger.handlers
                        if isinstance(h, logging.handlers.RotatingFileHandler)]
            handler = rotating[0]
            assert handler.maxBytes >= 1024 * 1024
            assert handler.backupCount >= 1
            _reset_logging_state_for_tests()

    def test_log_file_created_in_specified_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            log_files = list(Path(tmpdir).glob("uasset_read-*.log"))
            assert len(log_files) == 1
            _reset_logging_state_for_tests()
