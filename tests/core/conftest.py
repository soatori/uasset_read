"""tests/core 共享 fixture。"""
import pytest


@pytest.fixture(autouse=True)
def reset_project_logging_after_each():
    """每个测试结束后重置 project_logging 全局状态。

    parse_package() 调用 configure_project_logging() 会设置
    package_logger.propagate=False，导致后续测试的 caplog
    无法捕获日志。此 fixture 在每个测试完成后立即恢复状态，
    防止全局日志配置泄漏到其他测试模块。
    """
    yield
    from uasset_read.project_logging import _reset_logging_state_for_tests
    _reset_logging_state_for_tests()
