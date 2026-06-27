"""内存安全模块阈值测试。"""
from uasset_read.memory_safety import (
    PROCESS_RSS_HIGH_WATERMARK_MB,
    PROCESS_RSS_CRITICAL_MB,
    MEMORY_HIGH_WATERMARK,
    MEMORY_CRITICAL_WATERMARK,
)


def test_rss_high_watermark_is_1gb():
    """进程 RSS 高水位应为 1GB。"""
    assert PROCESS_RSS_HIGH_WATERMARK_MB == 1024


def test_rss_critical_is_2gb():
    """进程 RSS 临界值应为 2GB。"""
    assert PROCESS_RSS_CRITICAL_MB == 2048


def test_memory_high_watermark_is_60_percent():
    """系统内存高水位应为 60%。"""
    assert MEMORY_HIGH_WATERMARK == 0.6


def test_memory_critical_watermark_is_75_percent():
    """系统内存临界值应为 75%。"""
    assert MEMORY_CRITICAL_WATERMARK == 0.75


def test_parse_single_uses_memory_guard():
    """parse_single 应使用 MemoryGuard 上下文管理器。"""
    import inspect
    from uasset_read.core import parse_single
    source = inspect.getsource(parse_single)
    assert "MemoryGuard" in source, "parse_single 应引用 MemoryGuard"


def test_conftest_teardown_calls_cleanup():
    """conftest 的 pytest_runtest_teardown 应调用 cleanup_after_parse。"""
    import inspect
    from tests.conftest import pytest_runtest_teardown
    source = inspect.getsource(pytest_runtest_teardown)
    assert "cleanup_after_parse" in source, "teardown 应调用 cleanup_after_parse"
