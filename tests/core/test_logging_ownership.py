import importlib
import logging

import pytest

from uasset_read.config import LogConfig
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


@pytest.mark.parametrize("entrypoint", ["parse_package", "parse_uasset_with_linker"])
def test_low_level_parse_defaults_do_not_configure_file_logging(monkeypatch, entrypoint):
    parse_module = importlib.import_module("uasset_read.parse_uasset")
    calls = []

    monkeypatch.setattr(
        parse_module,
        "configure_project_logging",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(parse_module, "_parse_package_core", lambda *args, **kwargs: None)

    getattr(parse_module, entrypoint)("missing.uasset")

    assert calls == []
