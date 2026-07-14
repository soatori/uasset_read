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
