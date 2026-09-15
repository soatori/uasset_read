"""Tests for memory_safety.reserve_memory."""

from uasset_read.memory_safety import MemoryLimitExceeded, reserve_memory


def test_reserve_memory_single_read_limit():
    try:
        reserve_memory(17 * 1024 * 1024, "test", "a")
    except MemoryLimitExceeded:
        return
    raise AssertionError("expected MemoryLimitExceeded")


def test_reserve_memory_accumulates():
    total = reserve_memory(10, "t", "a")
    total = reserve_memory(10, "t", "a", total_decompressed=total)
    assert total == 20


def test_reserve_memory_rejects_negative():
    try:
        reserve_memory(-100, "unit")
    except MemoryLimitExceeded as e:
        assert "negative" in str(e)
        return
    raise AssertionError("expected MemoryLimitExceeded")


def test_reserve_memory_total_limit():
    big = 16 * 1024 * 1024  # at single-read limit, not over it
    total = reserve_memory(big, "t", "a")
    for _ in range(15):  # 16 * 16MB = 256MB exactly
        total = reserve_memory(big, "t", "a", total_decompressed=total)
    assert total == 256 * 1024 * 1024
    try:
        reserve_memory(big, "t", "a", total_decompressed=total)
    except MemoryLimitExceeded:
        return
    raise AssertionError("expected MemoryLimitExceeded")
