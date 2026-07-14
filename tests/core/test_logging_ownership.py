import importlib
import logging

import pytest

import uasset_read
from uasset_read.config import LogConfig
from uasset_read import core
from uasset_read.core import _configure_logging
from uasset_read.project_logging import _reset_logging_state_for_tests


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
