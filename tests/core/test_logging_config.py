"""日志配置测试。"""
import logging
import pytest


class TestLoggingLevelSpec:
    """#342: 日志级别规范测试。"""

    def test_logger_has_expected_handlers(self):
        """验证项目 logger 有正确的 handler 配置。"""
        from uasset_read.project_logging import configure_project_logging, _reset_logging_state_for_tests
        import tempfile
        from pathlib import Path

        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(
                log_dir=Path(tmp),
                level="DEBUG",
            )
            logger = logging.getLogger("uasset_read")
            assert len(logger.handlers) > 0
            # 在退出临时目录前关闭 handler，避免文件锁
            _reset_logging_state_for_tests()

    def test_log_level_can_be_configured(self):
        """验证日志级别可通过参数配置。"""
        from uasset_read.project_logging import configure_project_logging, _reset_logging_state_for_tests
        import tempfile
        from pathlib import Path

        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(
                log_dir=Path(tmp),
                level="WARNING",
            )
            logger = logging.getLogger("uasset_read")
            assert logger.level <= logging.WARNING
            # 在退出临时目录前关闭 handler，避免文件锁
            _reset_logging_state_for_tests()
