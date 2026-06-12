"""tests/test_array_count_check.py — 数组 count 越界诊断测试

验证 read_validated_count 在 count 为负数或超过上限时：
1. 不抛出异常（不导致崩溃）
2. 记录诊断信息（count、位置、上限）
3. 返回 0（调用方产生空集合）
"""
import io
import logging
from unittest.mock import MagicMock

from uasset_read.parsers.utils import read_validated_count


def _make_archive_with_i32(value: int) -> MagicMock:
    """创建 mock FArchive，read_i32 返回指定值，tell 返回固定偏移。"""
    archive = MagicMock()
    archive.read_i32.return_value = value
    archive.tell.return_value = 0x1000
    return archive


# ---- 负数 count ----

def test_negative_count_returns_zero():
    """负数 count 应返回 0 而非抛出异常"""
    archive = _make_archive_with_i32(-1)
    result = read_validated_count(archive, 10_000, "测试数组")
    assert result == 0


def test_large_negative_count_returns_zero():
    """大负数 count（如 -999999）应返回 0"""
    archive = _make_archive_with_i32(-999999)
    result = read_validated_count(archive, 10_000, "测试数组")
    assert result == 0


def test_int32_min_returns_zero():
    """INT32_MIN (-2147483648) 应返回 0"""
    archive = _make_archive_with_i32(-2147483648)
    result = read_validated_count(archive, 10_000, "测试数组")
    assert result == 0


# ---- 超过上限 count ----

def test_count_exceeding_max_returns_zero():
    """超过 MAX_PROPERTY_COUNT 的 count 应返回 0"""
    archive = _make_archive_with_i32(10_001)
    result = read_validated_count(archive, 10_000, "MapProperty 条目数量")
    assert result == 0


def test_count_exceeding_max_array_returns_zero():
    """超过 MAX_ARRAY_COUNT 的 count 应返回 0"""
    archive = _make_archive_with_i32(1_000_001)
    result = read_validated_count(archive, 1_000_000, "数组数量")
    assert result == 0


def test_int32_max_exceeds_property_count():
    """INT32_MAX (2147483647) 远超 10_000 上限，应返回 0"""
    archive = _make_archive_with_i32(2147483647)
    result = read_validated_count(archive, 10_000, "SetProperty 元素数量")
    assert result == 0


# ---- 正常值 ----

def test_zero_count_returns_zero():
    """count=0 是有效值，应返回 0"""
    archive = _make_archive_with_i32(0)
    result = read_validated_count(archive, 10_000, "测试数组")
    assert result == 0


def test_normal_count_passes_through():
    """正常 count（如 5）应原样返回"""
    archive = _make_archive_with_i32(5)
    result = read_validated_count(archive, 10_000, "测试数组")
    assert result == 5


def test_count_at_max_boundary():
    """count 恰好等于 max_count 是有效值"""
    archive = _make_archive_with_i32(10_000)
    result = read_validated_count(archive, 10_000, "测试数组")
    assert result == 10_000


def test_count_just_above_max():
    """count = max_count + 1 应返回 0"""
    archive = _make_archive_with_i32(10_001)
    result = read_validated_count(archive, 10_000, "测试数组")
    assert result == 0


# ---- 诊断日志 ----

def test_negative_count_logs_warning(caplog):
    """负数 count 应记录 WARNING 日志，包含 count、位置、上限"""
    archive = _make_archive_with_i32(-5)
    with caplog.at_level(logging.WARNING):
        read_validated_count(archive, 10_000, "数组数量")

    assert any("数量为负数" in r.message for r in caplog.records)
    assert any("-5" in r.message for r in caplog.records)
    assert any("0x1000" in r.message for r in caplog.records)
    assert any("10000" in r.message for r in caplog.records)


def test_count_exceeds_max_logs_warning(caplog):
    """超过上限的 count 应记录 WARNING 日志，包含 count 和上限"""
    archive = _make_archive_with_i32(50_000)
    with caplog.at_level(logging.WARNING):
        read_validated_count(archive, 10_000, "MapProperty 条目数量")

    assert any("数量超过最大值" in r.message for r in caplog.records)
    assert any("50000" in r.message for r in caplog.records)
    assert any("10000" in r.message for r in caplog.records)


def test_normal_count_no_warning(caplog):
    """正常 count 不应记录任何警告"""
    archive = _make_archive_with_i32(100)
    with caplog.at_level(logging.WARNING):
        read_validated_count(archive, 10_000, "测试数组")

    assert len([r for r in caplog.records if r.levelno >= logging.WARNING]) == 0


# ---- 不抛出异常 ----

def test_negative_count_no_exception():
    """负数 count 不应抛出任何异常"""
    archive = _make_archive_with_i32(-1)
    try:
        read_validated_count(archive, 10_000, "测试数组")
    except Exception as e:
        raise AssertionError(f"不应抛出异常，但得到: {type(e).__name__}: {e}")


def test_exceeds_max_no_exception():
    """超过上限的 count 不应抛出任何异常"""
    archive = _make_archive_with_i32(999_999_999)
    try:
        read_validated_count(archive, 10_000, "测试数组")
    except Exception as e:
        raise AssertionError(f"不应抛出异常，但得到: {type(e).__name__}: {e}")
