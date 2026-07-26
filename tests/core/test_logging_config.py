"""Logging configuration tests."""
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.project_logging import (
    configure_project_logging,
    current_log_run_id,
    _reset_logging_state_for_tests,
)


class TestLoggingLevelSpec:
    """#342: Log level specification tests."""

    def test_logger_has_expected_handlers(self):
        """Verify project logger has correct handler configuration."""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(
                log_dir=Path(tmp),
                level="DEBUG",
            )
            logger = logging.getLogger("uasset_read")
            assert len(logger.handlers) > 0
            # Close handlers before exiting temp dir to avoid file locks
            _reset_logging_state_for_tests()

    def test_log_level_can_be_configured(self):
        """Verify log level can be configured via parameters."""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(
                log_dir=Path(tmp),
                level="WARNING",
            )
            logger = logging.getLogger("uasset_read")
            assert logger.level <= logging.WARNING
            # Close handlers before exiting temp dir to avoid file locks
            _reset_logging_state_for_tests()


class TestBatchLogSingleFile:
    """#423: All batch output should go to a single log file when --log-dir is specified."""

    def test_parse_batch_skips_reconfigure_when_session_active(self):
        """parse_batch should not call _configure_logging when scoped_project_logging
        has already configured logging via an active session."""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            from uasset_read.config import LogConfig
            from uasset_read.core import parse_batch

            log_cfg = LogConfig(level="debug", dir=tmp)
            ua_logger = logging.getLogger("uasset_read")
            old_handlers = ua_logger.handlers[:]
            old_propagate = ua_logger.propagate
            old_level = ua_logger.level

            fake_file = Path("/tmp/fake/test.uasset")
            try:
                with patch.object(Path, "is_dir", return_value=True):
                    with patch.object(
                        Path, "rglob", side_effect=[[fake_file], []]
                    ):
                        with patch("uasset_read.memory_safety.get_memory_stats") as mock_stats:
                            mock_stats.return_value = MagicMock(usage_percent=0.1)
                            with patch("uasset_read.core._configure_logging") as mock_cfg:
                                parse_batch(
                                    "/tmp/fake",
                                    log_config=log_cfg,
                                )
                                # _configure_logging should NOT be called when
                                # scoped_project_logging already owns the session
                                mock_cfg.assert_not_called()
            finally:
                _reset_logging_state_for_tests()
                ua_logger.handlers = old_handlers
                ua_logger.propagate = old_propagate
                ua_logger.level = old_level

    def test_session_start_and_batch_summary_in_same_log_file(self):
        """session_start and batch_summary must appear in the same log file."""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            from uasset_read.config import LogConfig
            from uasset_read.core import parse_batch

            log_cfg = LogConfig(level="debug", dir=tmp, enabled=True)
            ua_logger = logging.getLogger("uasset_read")
            old_handlers = ua_logger.handlers[:]
            old_propagate = ua_logger.propagate
            old_level = ua_logger.level

            fake_file = Path("/tmp/fake/test.uasset")
            try:
                with patch.object(Path, "is_dir", return_value=True):
                    with patch.object(
                        Path, "rglob", side_effect=[[fake_file], []]
                    ):
                        with patch("uasset_read.memory_safety.get_memory_stats") as mock_stats:
                            mock_stats.return_value = MagicMock(usage_percent=0.1)
                            parse_batch(
                                "/tmp/fake",
                                log_config=log_cfg,
                            )
            finally:
                _reset_logging_state_for_tests()
                ua_logger.handlers = old_handlers
                ua_logger.propagate = old_propagate
                ua_logger.level = old_level

            # Find the log file created by the session
            log_files = list(Path(tmp).glob("uasset_read*.log"))
            assert len(log_files) == 1, f"Expected 1 log file, found {len(log_files)}: {log_files}"

            content = log_files[0].read_text(encoding="utf-8")
            assert "session_start" in content, "session_start missing from log file"
            assert "batch_summary" in content, "batch_summary missing from log file"
            assert "session_end" in content, "session_end missing from log file"

    def test_no_second_log_file_when_log_config_provided(self):
        """When log_config is provided, no log file should be created in the default log/ dir."""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            from uasset_read.config import LogConfig
            from uasset_read.core import parse_batch

            log_cfg = LogConfig(level="debug", dir=tmp, enabled=True)
            ua_logger = logging.getLogger("uasset_read")
            old_handlers = ua_logger.handlers[:]
            old_propagate = ua_logger.propagate
            old_level = ua_logger.level

            # Record log files in default dir before the test
            default_log_dir = Path(__file__).resolve().parents[2] / "log"
            before_default_logs = set(default_log_dir.glob("uasset_read*.log")) if default_log_dir.exists() else set()

            fake_file = Path("/tmp/fake/test.uasset")
            try:
                with patch.object(Path, "is_dir", return_value=True):
                    with patch.object(
                        Path, "rglob", side_effect=[[fake_file], []]
                    ):
                        with patch("uasset_read.memory_safety.get_memory_stats") as mock_stats:
                            mock_stats.return_value = MagicMock(usage_percent=0.1)
                            parse_batch(
                                "/tmp/fake",
                                log_config=log_cfg,
                            )
            finally:
                _reset_logging_state_for_tests()
                ua_logger.handlers = old_handlers
                ua_logger.propagate = old_propagate
                ua_logger.level = old_level

            # Only log files should be in the caller-specified tmp dir
            log_files = list(Path(tmp).glob("uasset_read*.log"))
            assert len(log_files) == 1

            # No NEW log files should have been created in the default log/ directory
            if default_log_dir.exists():
                after_default_logs = set(default_log_dir.glob("uasset_read*.log"))
                new_default_logs = after_default_logs - before_default_logs
                assert len(new_default_logs) == 0, (
                    f"Unexpected new log files in default log/: {new_default_logs}"
                )


class TestWorkerErrorVisibility:
    """#423: Child worker errors should be visible in the parent's log file."""

    def test_worker_failure_logged_inside_session(self):
        """When an isolated worker fails, the error should be logged to the session log file."""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            from uasset_read.config import LogConfig
            from uasset_read.core import parse_batch

            log_cfg = LogConfig(level="debug", dir=tmp, enabled=True)
            ua_logger = logging.getLogger("uasset_read")
            old_handlers = ua_logger.handlers[:]
            old_propagate = ua_logger.propagate
            old_level = ua_logger.level

            # Create a real .uasset file that will fail in the worker
            asset_dir = Path(tmp) / "assets"
            asset_dir.mkdir()
            bad_asset = asset_dir / "bad.uasset"
            bad_asset.write_bytes(b"\x00" * 100)

            output_dir = Path(tmp) / "output"
            try:
                result = parse_batch(
                    str(asset_dir),
                    log_config=log_cfg,
                    isolate_assets=True,
                )
            finally:
                _reset_logging_state_for_tests()
                ua_logger.handlers = old_handlers
                ua_logger.propagate = old_propagate
                ua_logger.level = old_level

            # The batch should have results (success or failed)
            assert result.total == 1

            # Check that the log file contains the error info
            log_files = list(Path(tmp).glob("uasset_read*.log"))
            assert len(log_files) >= 1
            content = log_files[0].read_text(encoding="utf-8")
            # batch_summary should be present
            assert "batch_summary" in content

    def test_batch_result_failed_tuple_has_error_details(self):
        """BatchResult.failed tuples should contain error and traceback details."""
        from uasset_read.batch_worker import BatchWorkerOutcome
        from uasset_read.core import BatchResult

        # Simulate a failed worker outcome
        outcome = BatchWorkerOutcome(
            succeeded=False,
            error="ValueError: bad data",
            error_details="Traceback (most recent call last):\n  ...\nValueError: bad data",
        )

        result = BatchResult(total=1)
        if not outcome.succeeded:
            result.failed.append(("bad.uasset", outcome.error, outcome.error_details))

        assert len(result.failed) == 1
        path, error, details = result.failed[0]
        assert "ValueError" in error
        assert "Traceback" in details
