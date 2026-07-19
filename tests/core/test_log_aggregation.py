"""_RepeatedDebugFilter 聚合计数与 get_summary 测试。"""

from __future__ import annotations

import logging

from uasset_read.project_logging import _RepeatedDebugFilter


def test_debug_aggregation_shows_counts():
    """重复 DEBUG 消息超过 repeat_limit 后应被抑制，message_counts 记录完整次数。"""
    logger = logging.getLogger("test_aggregation")
    logger.setLevel(logging.DEBUG)
    filter_obj = _RepeatedDebugFilter(repeat_limit=3)
    logger.addFilter(filter_obj)

    for _ in range(10):
        logger.debug("read_name: index out of range")

    assert filter_obj.suppressed_count == 7
    assert "read_name: index out of range" in filter_obj.message_counts
    assert filter_obj.message_counts["read_name: index out of range"] == 10
    logger.removeFilter(filter_obj)


def test_get_summary_returns_empty_when_no_suppression():
    """未发生抑制时 get_summary 返回空字符串。"""
    filter_obj = _RepeatedDebugFilter(repeat_limit=5)
    assert filter_obj.get_summary() == ""


def test_get_summary_contains_suppressed_info():
    """抑制发生后 get_summary 包含抑制次数。"""
    logger = logging.getLogger("test_aggregation_summary")
    logger.setLevel(logging.DEBUG)
    filter_obj = _RepeatedDebugFilter(repeat_limit=2)
    logger.addFilter(filter_obj)

    for _ in range(6):
        logger.debug("some repeated message")

    summary = filter_obj.get_summary()
    assert "some repeated message" in summary
    assert "suppressed 4 times" in summary
    logger.removeFilter(filter_obj)


def test_debug_messages_still_tracked_in_legacy_counts():
    """DEBUG 消息仍通过旧 counts 字典跟踪（summaries() 兼容）。"""
    logger = logging.getLogger("test_aggregation_debug")
    logger.setLevel(logging.DEBUG)
    filter_obj = _RepeatedDebugFilter(repeat_limit=3)
    logger.addFilter(filter_obj)

    for _ in range(6):
        logger.debug("debug repeated message")

    # 旧 counts 字典使用 tuple key
    assert len(filter_obj.counts) == 1
    legacy_count = list(filter_obj.counts.values())[0]
    assert legacy_count == 6
    # 新 message_counts 也记录了
    assert filter_obj.message_counts["debug repeated message"] == 6
    assert filter_obj.suppressed_count == 3
    logger.removeFilter(filter_obj)


def test_warning_messages_tracked_but_not_suppressed():
    """WARNING 消息被 message_counts 跟踪但不被抑制（仅 DEBUG 受限）。"""
    logger = logging.getLogger("test_aggregation_warn")
    logger.setLevel(logging.DEBUG)
    filter_obj = _RepeatedDebugFilter(repeat_limit=2)
    logger.addFilter(filter_obj)

    for _ in range(5):
        logger.warning("warning should pass through")

    # WARNING 不被抑制，suppressed_count 仍为 0
    assert filter_obj.suppressed_count == 0
    assert filter_obj.message_counts["warning should pass through"] == 5
    assert filter_obj.get_summary() == ""
    logger.removeFilter(filter_obj)
