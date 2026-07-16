import io
import logging
from pathlib import Path

import pytest

from uasset_read import project_logging

_reset_logging_state_for_tests = project_logging._reset_logging_state_for_tests
configure_project_logging = project_logging.configure_project_logging


@pytest.fixture(autouse=True)
def reset_project_logging():
    _reset_logging_state_for_tests()
    yield
    _reset_logging_state_for_tests()


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


def project_logging_config(**kwargs):
    from uasset_read.config import LogConfig

    return LogConfig(**kwargs)
