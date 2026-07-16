"""日志文件优化测试。"""
import logging
import logging.handlers
import os
import tempfile
from pathlib import Path

import pytest
from uasset_read.project_logging import (
    setup_logging,
    _build_log_path,
    _reset_logging_state_for_tests,
)


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
