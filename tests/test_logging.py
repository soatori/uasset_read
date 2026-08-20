"""Tests for project_logging enhancements: log_event, log_stage_timing, JSONFormatter, SamplingFilter."""

from __future__ import annotations

import json
import logging
import sys

import pytest

from uasset_read.project_logging import (
    JSONFormatter,
    SamplingFilter,
    current_log_run_id,
    log_context,
    log_event,
    log_stage_timing,
    project_logging_session,
)


class TestLogEvent:
    """log_event() emits structured key=value output."""

    def test_log_event_basic(self, caplog):
        logger = logging.getLogger("test_log_event")
        with caplog.at_level(logging.INFO, logger="test_log_event"):
            log_event(logger, logging.INFO, "parse_start", asset="BP_Player")
        assert "event=parse_start asset=BP_Player" in caplog.text

    def test_log_event_sorted_fields(self, caplog):
        logger = logging.getLogger("test_log_event_sorted")
        with caplog.at_level(logging.INFO, logger="test_log_event_sorted"):
            log_event(logger, logging.INFO, "test", zebra="z", alpha="a")
        assert "event=test alpha=a zebra=z" in caplog.text

    def test_log_event_no_fields(self, caplog):
        logger = logging.getLogger("test_log_event_no_fields")
        with caplog.at_level(logging.INFO, logger="test_log_event_no_fields"):
            log_event(logger, logging.INFO, "simple")
        assert "event=simple" in caplog.text

    def test_log_event_multiple_fields(self, caplog):
        logger = logging.getLogger("test_log_event_multi")
        with caplog.at_level(logging.INFO, logger="test_log_event_multi"):
            log_event(logger, logging.INFO, "done", total=10, success=8, failed=2)
        assert "event=done" in caplog.text
        assert "failed=2" in caplog.text
        assert "success=8" in caplog.text
        assert "total=10" in caplog.text


class TestStageTiming:
    """log_stage_timing() works as context manager and decorator."""

    def test_timing_as_context_manager(self, caplog):
        logger = logging.getLogger("test_timing_cm")
        with caplog.at_level(logging.DEBUG, logger="test_timing_cm"):
            with log_stage_timing(logger, "parse", asset="test.uasset"):
                pass
        assert "stage_start stage=parse" in caplog.text
        assert "stage_end stage=parse status=success duration_ms=" in caplog.text

    def test_timing_logs_error_on_exception(self, caplog):
        logger = logging.getLogger("test_timing_err")
        with caplog.at_level(logging.DEBUG, logger="test_timing_err"):
            with pytest.raises(ValueError):
                with log_stage_timing(logger, "fail_stage"):
                    raise ValueError("boom")
        assert "stage_end stage=fail_stage status=error" in caplog.text

    def test_timing_as_decorator(self, caplog):
        logger = logging.getLogger("test_timing_dec")

        @log_stage_timing(logger, "decorated")
        def my_func():
            return 42

        with caplog.at_level(logging.DEBUG, logger="test_timing_dec"):
            result = my_func()
        assert result == 42
        assert "stage_end stage=decorated status=success" in caplog.text
        assert my_func.__name__ == "my_func"

    def test_timing_decorator_preserves_args(self, caplog):
        logger = logging.getLogger("test_timing_args")

        @log_stage_timing(logger, "add")
        def add(a, b):
            return a + b

        with caplog.at_level(logging.DEBUG, logger="test_timing_args"):
            result = add(3, 4)
        assert result == 7


class TestJSONFormatter:
    """JSONFormatter produces valid single-line JSON per record."""

    def test_json_output_structure(self):
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
        record = logging.LogRecord(
            name="uasset_read",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.run_id = "abc123"
        record.process_id = 1234
        record.asset = "BP_Player"
        record.stage = "link"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["run"] == "abc123"
        assert parsed["asset"] == "BP_Player"
        assert parsed["stage"] == "link"
        assert parsed["msg"] == "test message"
        assert "ts" in parsed

    def test_json_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="uasset_read",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="failed",
                args=(),
                exc_info=sys.exc_info(),
            )
            record.run_id = "-"
            record.process_id = 0
            record.asset = "-"
            record.stage = "-"

        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exc" in parsed
        assert "ValueError: test error" in parsed["exc"]


class TestSamplingFilter:
    """SamplingFilter deterministically drops DEBUG records."""

    def test_rate_1_keeps_all(self):
        f = SamplingFilter(rate=1.0)
        record = logging.LogRecord("test", logging.DEBUG, "", 0, "msg", (), None)
        assert f.filter(record) is True

    def test_rate_0_drops_debug(self):
        f = SamplingFilter(rate=0.0)
        record = logging.LogRecord("test", logging.DEBUG, "", 0, "msg", (), None)
        assert f.filter(record) is False

    def test_rate_0_keeps_info(self):
        f = SamplingFilter(rate=0.0)
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        assert f.filter(record) is True

    def test_stable_hash_deterministic(self):
        assert SamplingFilter._stable_hash("hello") == SamplingFilter._stable_hash(
            "hello"
        )
        assert SamplingFilter._stable_hash("abc") != SamplingFilter._stable_hash("xyz")

    def test_rate_0_5_keeps_half(self):
        f = SamplingFilter(rate=0.5)
        kept = sum(
            1
            for i in range(1000)
            if f.filter(
                logging.LogRecord("test", logging.DEBUG, "", 0, f"msg_{i}", (), None)
            )
        )
        assert 300 < kept < 700  # ~500, allow wide margin


class TestLogContext:
    """log_context() sets asset/stage on LogRecords."""

    def test_context_sets_fields(self):
        from uasset_read.project_logging import _log_asset, _log_stage

        before_asset = _log_asset.get()
        before_stage = _log_stage.get()
        with log_context(asset="BP_Player", stage="link"):
            assert _log_asset.get() == "BP_Player"
            assert _log_stage.get() == "link"
        # Context restored after exiting
        assert _log_asset.get() == before_asset
        assert _log_stage.get() == before_stage
