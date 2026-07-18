"""错误处理综合测试 — 合并自 test_error_handling.py 和 test_error_handling_v2.py。

覆盖：tolerant_parse 基础行为与去重、异常类层次、_handle_parse_error 各分支、
_record_parse_stage_error 去重与诊断、BaseResult._error_keys 字段。
"""

import importlib
import sys
from unittest import mock

import pytest

from uasset_read.exceptions import (
    UAssetError,
    DecompressionError,
    LinkerError,
    ParseError,
    VersionError,
)
from uasset_read.memory_safety import MemoryLimitExceeded


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

class MockResult:
    def __init__(self):
        self.errors = []


class _FakeResult:
    """轻量 Mock，模拟 BaseResult/ParseResult 的必要字段。"""

    def __init__(self):
        self.errors: list[str] = []
        self.is_success: bool = True
        self.summary = None
        self.diagnostics: list = []
        self.graphs: list = []
        self._error_keys: set = set()  # 错误去重用


class _FakeArchive:
    """模拟 FArchive，为 _record_parse_stage_error 提供必要接口。"""

    def __init__(self, size: int = 1024, pos: int = 0):
        self._size = size
        self._pos = pos

    def total_size(self) -> int:
        return self._size

    def tell(self) -> int:
        return self._pos


# ===========================================================================
# 1. tolerant_parse — 基础行为
# ===========================================================================

def test_tolerant_parse_no_error():
    from uasset_read.core.error_handling import tolerant_parse
    result = MockResult()
    with tolerant_parse(result, "test"):
        pass
    assert result.errors == []


def test_tolerant_parse_with_error():
    from uasset_read.core.error_handling import tolerant_parse
    result = MockResult()
    with pytest.raises(ParseError):
        with tolerant_parse(result, "test"):
            raise ParseError("test error")
    assert len(result.errors) == 1
    assert "test error" in result.errors[0]


# ===========================================================================
# 2. tolerant_parse — 去重
# ===========================================================================

def test_tolerant_parse_dedup():
    """同一 ParseError 不会重复添加到 result.errors。"""
    from uasset_read.core.error_handling import tolerant_parse

    class _R:
        def __init__(self):
            self.errors: list[str] = []

    result = _R()
    # 用相同消息抛两次
    with pytest.raises(ParseError):
        with tolerant_parse(result, "stage"):
            raise ParseError("dup error")

    assert len(result.errors) == 1, f"期望 1 条错误，实际 {len(result.errors)}: {result.errors}"

    with pytest.raises(ParseError):
        with tolerant_parse(result, "stage"):
            raise ParseError("dup error")

    assert len(result.errors) == 1, f"去重失败，期望仍为 1 条，实际 {len(result.errors)}"


# ===========================================================================
# 3. 异常类层次与行为
# ===========================================================================

@pytest.mark.parametrize("exc_cls", [DecompressionError, LinkerError])
class TestExceptionHierarchy:
    """DecompressionError / LinkerError 继承自 UAssetError，可 raise 和 catch。"""

    def test_inherits_from_uasset_error(self, exc_cls):
        assert issubclass(exc_cls, UAssetError)

    def test_is_exception(self, exc_cls):
        assert issubclass(exc_cls, Exception)

    def test_raise_and_catch(self, exc_cls):
        with pytest.raises(UAssetError):
            raise exc_cls("test message")

    def test_catch_as_exception(self, exc_cls):
        """也能被基类 Exception 捕获。"""
        with pytest.raises(Exception):
            raise exc_cls("test message")


def test_exceptions_importable_from_package():
    """异常类可直接从 uasset_read.exceptions 顶层导入。"""
    import uasset_read.exceptions as mod

    assert hasattr(mod, "DecompressionError")
    assert hasattr(mod, "LinkerError")
    assert hasattr(mod, "ParseError")
    assert hasattr(mod, "VersionError")
    assert hasattr(mod, "UAssetError")


# ===========================================================================
# 4. _handle_parse_error — 各异常分支
# ===========================================================================

class TestHandleParseError:
    """覆盖 _handle_parse_error 的六个分支。

    不使用 mock.patch — 直接验证实际行为，避免 Python 3.10 模块名冲突。
    """

    def _call(self, exc, result, tolerant=True):
        """在 except 上下文中调用 _handle_parse_error，模拟实际调用链。

        _handle_parse_error 内部使用 bare raise，需要活跃的异常上下文。
        """
        mod = importlib.import_module("uasset_read.parse_uasset")
        _handle_parse_error = mod._handle_parse_error
        archive = _FakeArchive()
        try:
            raise exc
        except Exception as caught:
            _handle_parse_error(caught, result, archive, "test.uasset", tolerant)

    # -- VersionError -------------------------------------------------------

    def test_version_error_records_and_sets_failure(self):
        result = _FakeResult()
        self._call(VersionError("unsupported version"), result)

        assert result.is_success is False
        assert len(result.errors) > 0
        assert any("VersionError" in e for e in result.errors)

    # -- ParseError (有 partial_result) -------------------------------------

    def test_parse_error_extracts_partial_result(self):
        result = _FakeResult()
        partial = {"graphs": [{"name": "partial_graph"}]}
        exc = ParseError("parse failed", partial_result=partial)
        self._call(exc, result)

        assert result.is_success is False
        assert result.graphs == [{"name": "partial_graph"}]
        assert len(result.errors) > 0

    def test_parse_error_no_partial_result(self):
        result = _FakeResult()
        exc = ParseError("parse failed without partial")
        self._call(exc, result)

        assert result.is_success is False
        assert len(result.errors) > 0

    # -- MemoryError --------------------------------------------------------

    def test_memory_error_records_and_sets_failure(self):
        result = _FakeResult()
        self._call(MemoryError("out of memory"), result)

        assert result.is_success is False
        assert any("MemoryError" in e for e in result.errors)

    # -- 其他异常 -----------------------------------------------------------

    def test_unexpected_error_records_and_sets_failure(self):
        result = _FakeResult()
        self._call(RuntimeError("something broke"), result)

        assert result.is_success is False
        assert len(result.errors) > 0

    # -- MemoryLimitExceeded 直接 re-raise ----------------------------------

    def test_memory_limit_exceeded_reraises(self):
        result = _FakeResult()
        exc = MemoryLimitExceeded(
            asset_path="test.uasset",
            stage="parse",
            current_rss_mb=2048.0,
            limit_mb=1024.0,
        )
        with pytest.raises(MemoryLimitExceeded):
            self._call(exc, result)
        # 不应修改 result
        assert result.errors == []
        assert result.is_success is True

    # -- tolerant=False 时 re-raise -----------------------------------------

    def test_not_tolerant_reraises(self):
        result = _FakeResult()
        exc = ParseError("fatal parse error")
        with pytest.raises(ParseError):
            self._call(exc, result, tolerant=False)
        # re-raise 前仍记录了错误
        assert result.is_success is False
        assert len(result.errors) > 0


# ===========================================================================
# 5. _record_parse_stage_error — 去重与诊断
# ===========================================================================

class TestRecordParseStageError:
    """覆盖 _record_parse_stage_error 的核心行为。"""

    def _call(self, result, archive=None, stage="parse", field="test", error=None):
        from uasset_read.parse_stages import _record_parse_stage_error
        if error is None:
            error = ValueError("test error")
        _record_parse_stage_error(result, archive, "test.uasset", stage, field, error)

    def test_first_error_adds_to_errors(self):
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, error=ValueError("first error"))

        assert len(result.errors) == 1
        assert "first error" in result.errors[0]
        assert result.is_success is False

    def test_duplicate_error_not_added(self):
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, error=ValueError("dup error"))
        self._call(result, archive, error=ValueError("dup error"))

        assert len(result.errors) == 1

    def test_different_errors_all_added(self):
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, error=ValueError("error A"))
        self._call(result, archive, error=ValueError("error B"))

        assert len(result.errors) == 2

    def test_always_appends_diagnostic(self):
        result = _FakeResult()
        archive = _FakeArchive(size=2048, pos=512)

        self._call(result, archive, error=ValueError("diagnostic test"))

        assert len(result.diagnostics) == 1
        diag = result.diagnostics[0]
        assert diag.kind == "parse_stage_error"
        assert diag.asset_path == "test.uasset"
        assert diag.module == "parse"
        assert diag.field == "test"
        assert diag.current_pos == 512
        assert diag.file_size == 2048
        assert diag.source == "_parse_package_core"
        assert "diagnostic test" in diag.error
        assert diag.fallback_used is True

    def test_diagnostic_added_even_for_duplicate_error(self):
        """去重不影响 diagnostic 记录——重复错误仍会产生新的 diagnostic。"""
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, error=ValueError("dup"))
        self._call(result, archive, error=ValueError("dup"))

        assert len(result.errors) == 1
        assert len(result.diagnostics) == 2

    def test_archive_none_handled(self):
        """archive 为 None 时不会崩溃。"""
        result = _FakeResult()
        self._call(result, archive=None, error=ValueError("no archive"))

        assert len(result.errors) == 1
        assert len(result.diagnostics) == 1

    def test_different_exception_types_same_message_not_filtered(self):
        """不同异常类型相同消息不应被误过滤（Issue #359 核心场景）。"""
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, stage="parse", error=ValueError("same message"))
        self._call(result, archive, stage="parse", error=ParseError("same message"))

        assert len(result.errors) == 2, (
            f"不同异常类型相同消息应保留两条，实际 {len(result.errors)}: {result.errors}"
        )

    def test_same_exception_different_stage_not_filtered(self):
        """相同异常类型和消息但不同阶段不应被误过滤。"""
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, stage="stage_a", error=ValueError("msg"))
        self._call(result, archive, stage="stage_b", error=ValueError("msg"))

        assert len(result.errors) == 2, (
            f"不同阶段相同错误应保留两条，实际 {len(result.errors)}: {result.errors}"
        )


# ===========================================================================
# 6. BaseResult._error_keys 正式字段
# ===========================================================================

class TestErrorKeysField:
    """验证 _error_keys 是 BaseResult 的正式字段而非动态属性。"""

    def test_error_keys_exists_on_base_result(self):
        """BaseResult 应有 _error_keys 类字段。"""
        from uasset_read.models.result import BaseResult

        result = BaseResult()
        assert hasattr(result, "_error_keys")
        assert isinstance(result._error_keys, set)
        assert len(result._error_keys) == 0

    def test_error_keys_exists_on_parse_result(self):
        """ParseResult 继承 BaseResult，应有 _error_keys 字段。"""
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        assert hasattr(result, "_error_keys")
        assert isinstance(result._error_keys, set)

    def test_error_keys_tracks_unique_errors(self):
        """相同错误 key 不应重复添加。"""
        from uasset_read.models.result import BaseResult

        result = BaseResult()
        key = ("ValueError", "read_header", "ValueError: invalid")
        result._error_keys.add(key)
        result._error_keys.add(key)  # 重复添加

        assert len(result._error_keys) == 1

    def test_error_keys_different_types_not_filtered(self):
        """不同异常类型的 key 应该共存。"""
        from uasset_read.models.result import BaseResult

        result = BaseResult()
        key1 = ("ValueError", "stage", "ValueError: msg")
        key2 = ("TypeError", "stage", "TypeError: msg")

        result._error_keys.add(key1)
        result._error_keys.add(key2)

        assert len(result._error_keys) == 2
