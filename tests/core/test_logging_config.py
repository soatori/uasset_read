"""Tests for LogConfig.format field and configure_project_logging format param."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pytest

from uasset_read.config import LogConfig
from uasset_read.project_logging import (
    JSONFormatter,
    configure_project_logging,
    _reset_logging_state_for_tests,
)


class TestLogConfigFormat:
    """LogConfig.format field."""

    def test_default_format_is_text(self):
        cfg = LogConfig()
        assert cfg.format == "text"

    def test_json_format_in_kwargs(self):
        cfg = LogConfig(format="json")
        kwargs = cfg.to_configure_kwargs()
        assert kwargs.get("format") == "json"

    def test_text_format_not_in_kwargs(self):
        cfg = LogConfig(format="text")
        kwargs = cfg.to_configure_kwargs()
        assert "format" not in kwargs


class TestConfigureLoggingFormat:
    """configure_project_logging() format parameter."""

    def test_json_format_uses_json_formatter(self):
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(log_dir=Path(tmp), level="DEBUG", format="json")
            logger = logging.getLogger("uasset_read")
            handler = logger.handlers[-1]
            assert isinstance(handler.formatter, JSONFormatter)
            _reset_logging_state_for_tests()

    def test_text_format_uses_standard_formatter(self):
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(log_dir=Path(tmp), level="DEBUG", format="text")
            logger = logging.getLogger("uasset_read")
            handler = logger.handlers[-1]
            assert not isinstance(handler.formatter, JSONFormatter)
            _reset_logging_state_for_tests()
