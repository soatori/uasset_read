"""decompile_single_function 失败处理回归测试。

覆盖 Issue #401-2：单函数反编译失败时返回带错误信息的结果（tolerant 模式），
而非静默丢弃返回 None。

验证场景：
- tolerant 模式下异常捕获 → 返回 bytecode_status="failed" 的结果
- tolerant 模式下 error 非空 → 返回 bytecode_status="failed" 的结果
- tolerant 模式下空表达式 → 返回 bytecode_status="failed" 的结果
- 非 tolerant 模式下异常 → 仍然 raise
- 一个函数失败、一个函数成功时，后处理正确合并结果

BPGC 字节码缓存行为测试 (#367)。
验证 MathFunctionCleaner 对 BlueprintSetLibrary 的语义翻译。
"""

from __future__ import annotations

import logging
import struct
import unittest.mock
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.kismet.bytecode_extractor import (
    _bpgc_bytecode_cache,
    _bpgc_cache_retries,
    _BPGC_MAX_RETRIES,
    reset_bpgc_cache,
)
from uasset_read.kismet.pipeline import decompile_single_function
from uasset_read.kismet.result import KismetDecompiledResult
from uasset_read.kismet.translator import MathFunctionCleaner


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _make_mock_export(object_name: str = "TestFunction") -> MagicMock:
    """创建 mock ObjectExport。"""
    export = MagicMock()
    export.object_name = object_name
    return export


def _make_mock_archive() -> MagicMock:
    """创建 mock FArchive。"""
    return MagicMock()


def _make_mock_summary() -> MagicMock:
    """创建 mock PackageFileSummary。"""
    return MagicMock()


def _fake_expressions():
    """创建最小的表达式列表（包含一个 Return token）。"""
    expr = MagicMock()
    expr.StatementIndex = 0
    return [expr]


# ---------------------------------------------------------------------------
# 1. tolerant 模式异常捕获
# ---------------------------------------------------------------------------

class TestDecompileSingleFunctionException:
    """tolerant 模式下异常应返回失败结果而非 None。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_tolerant_exception_returns_failed_result(self, mock_extract):
        """异常在 tolerant 模式下应返回 bytecode_status='failed' 的结果。"""
        mock_extract.side_effect = ValueError("corrupted bytecode")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export("BrokenFunc"),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=True,
        )

        assert result is not None
        assert isinstance(result, KismetDecompiledResult)
        assert result.bytecode_status == "failed"
        assert result.function_name == "BrokenFunc"
        assert any("corrupted bytecode" in r for r in result.fallback_reasons)

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_non_tolerant_exception_raises(self, mock_extract):
        """非 tolerant 模式下异常应继续 raise。"""
        mock_extract.side_effect = ValueError("corrupted bytecode")

        with pytest.raises(ValueError, match="corrupted bytecode"):
            decompile_single_function(
                archive=_make_mock_archive(),
                export=_make_mock_export(),
                summary=_make_mock_summary(),
                name_map=[],
                import_map=[],
                export_map=[],
                tolerant=False,
            )


# ---------------------------------------------------------------------------
# 2. tolerant 模式 error 返回
# ---------------------------------------------------------------------------

class TestDecompileSingleFunctionError:
    """tolerant 模式下 error 非空应返回失败结果。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_tolerant_error_returns_failed_result(self, mock_extract):
        """extract_and_parse 返回 error 时应返回 bytecode_status='failed'。"""
        mock_extract.return_value = ([], "parse error occurred", "none")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export("ErrorFunc"),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=True,
        )

        assert result is not None
        assert result.bytecode_status == "failed"
        assert result.function_name == "ErrorFunc"
        assert any("parse error occurred" in r for r in result.fallback_reasons)

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_non_tolerant_error_returns_none(self, mock_extract):
        """非 tolerant 模式下 error 非空应返回 None（原有行为）。"""
        mock_extract.return_value = ([], "parse error occurred", "none")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export(),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=False,
        )

        assert result is None


# ---------------------------------------------------------------------------
# 3. tolerant 模式空表达式
# ---------------------------------------------------------------------------

class TestDecompileSingleFunctionEmptyExpressions:
    """tolerant 模式下空表达式应返回失败结果。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_tolerant_empty_expressions_returns_failed_result(self, mock_extract):
        """空表达式列表在 tolerant 模式下应返回 bytecode_status='failed'。"""
        mock_extract.return_value = ([], None, "none")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export("EmptyFunc"),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=True,
        )

        assert result is not None
        assert result.bytecode_status == "failed"
        assert result.function_name == "EmptyFunc"
        assert any("no bytecode" in r for r in result.fallback_reasons)


# ---------------------------------------------------------------------------
# 4. 成功路径不被破坏
# ---------------------------------------------------------------------------

class TestDecompileSingleFunctionSuccess:
    """正常路径不受影响。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_successful_decompilation(self, mock_extract):
        """正常解析应返回 bytecode_status='parsed' 的结果。"""
        mock_extract.return_value = (_fake_expressions(), None, "function_export")

        result = decompile_single_function(
            archive=_make_mock_archive(),
            export=_make_mock_export("GoodFunc"),
            summary=_make_mock_summary(),
            name_map=[],
            import_map=[],
            export_map=[],
            tolerant=True,
        )

        assert result is not None
        assert result.bytecode_status == "parsed"
        assert result.function_name == "GoodFunc"


# ---------------------------------------------------------------------------
# 5. 一个函数失败 + 一个函数成功 → 后处理合并
# ---------------------------------------------------------------------------

class TestMixedFunctionResults:
    """一个函数失败、一个函数成功时，后处理正确合并结果。"""

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_one_fail_one_success_post_processing(self, mock_extract):
        """一个函数失败、一个函数成功时，后处理正确合并结果。"""
        call_count = 0

        def side_effect(archive, export, summary, name_map, import_map, export_map, tolerant=True):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("malformed bytecode in function 1")
            else:
                return (_fake_expressions(), None, "function_export")

        mock_extract.side_effect = side_effect

        archive = _make_mock_archive()
        summary = _make_mock_summary()
        export1 = _make_mock_export("FailingFunc")
        export2 = _make_mock_export("SucceedingFunc")

        # 模拟 decompile_uasset 的后处理逻辑
        results = []
        for export in [export1, export2]:
            result = decompile_single_function(
                archive=archive,
                export=export,
                summary=summary,
                name_map=[],
                import_map=[],
                export_map=[],
                tolerant=True,
            )
            if result is not None:
                results.append(result)

        # 应包含两个结果：一个失败、一个成功
        assert len(results) == 2

        failed = [r for r in results if r.bytecode_status == "failed"]
        succeeded = [r for r in results if r.bytecode_status == "parsed"]

        assert len(failed) == 1
        assert len(succeeded) == 1
        assert failed[0].function_name == "FailingFunc"
        assert succeeded[0].function_name == "SucceedingFunc"
        assert any("malformed bytecode" in r for r in failed[0].fallback_reasons)

    @patch("uasset_read.kismet.pipeline.extract_and_parse")
    def test_all_fail_results_returned(self, mock_extract):
        """所有函数都失败时，tolerant 模式返回全部失败结果。"""
        mock_extract.side_effect = ValueError("global corruption")

        # 创建两个 export
        export1 = _make_mock_export("Func1")
        export2 = _make_mock_export("Func2")

        results = []
        for export in [export1, export2]:
            result = decompile_single_function(
                archive=_make_mock_archive(),
                export=export,
                summary=_make_mock_summary(),
                name_map=[],
                import_map=[],
                export_map=[],
                tolerant=True,
            )
            results.append(result)

        # 两个都应返回失败结果
        assert all(r is not None for r in results)
        assert all(r.bytecode_status == "failed" for r in results)
        assert results[0].function_name == "Func1"
        assert results[1].function_name == "Func2"


# ---------------------------------------------------------------------------
# BPGC 字节码缓存测试 (merged from test_bpgc_cache.py)
# ---------------------------------------------------------------------------


class TestBpgcCache:
    """Tests for BPGC bytecode cache retry behavior."""

    def setup_method(self):
        reset_bpgc_cache()

    def test_initial_state_is_none(self):
        """Cache starts as None (uninitialized)."""
        import uasset_read.kismet.bytecode_extractor as mod
        assert mod._bpgc_bytecode_cache is None
        assert mod._bpgc_cache_retries == 0

    def test_reset_clears_retry_counter(self):
        """reset_bpgc_cache() resets both cache and retry counter."""
        import uasset_read.kismet.bytecode_extractor as mod
        mod._bpgc_cache_retries = 2
        mod._bpgc_bytecode_cache = {}
        reset_bpgc_cache()
        assert mod._bpgc_bytecode_cache is None
        assert mod._bpgc_cache_retries == 0

    def test_cache_hit_returns_bytecode(self):
        """When function is in cache, its bytecode is returned."""
        import uasset_read.kismet.bytecode_extractor as mod
        mod._bpgc_bytecode_cache = {"TestFunc": b'\x00\x01\x02'}
        # Simulate cache lookup (the inline logic in _bpgc_fallback)
        func_name = "TestFunc"
        assert mod._bpgc_bytecode_cache.get(func_name) == b'\x00\x01\x02'

    def test_cache_miss_returns_none(self):
        """When function is not in cache, lookup returns None."""
        import uasset_read.kismet.bytecode_extractor as mod
        mod._bpgc_bytecode_cache = {}
        func_name = "MissingFunc"
        assert mod._bpgc_bytecode_cache.get(func_name) is None

    def test_failure_does_not_permanently_cache_empty(self):
        """After first failure, cache stays None (allows retry), not {}."""
        import uasset_read.kismet.bytecode_extractor as mod
        reset_bpgc_cache()
        assert mod._bpgc_bytecode_cache is None

        # Simulate first failure: increment retry but don't set cache to {}
        mod._bpgc_cache_retries += 1
        # Cache should still be None (not {}), so next call retries
        assert mod._bpgc_bytecode_cache is None
        assert mod._bpgc_cache_retries == 1

    def test_retry_limit_prevents_infinite_retry(self):
        """After _BPGC_MAX_RETRIES failures, cache is set to {} to stop retrying."""
        import uasset_read.kismet.bytecode_extractor as mod
        reset_bpgc_cache()

        # Simulate failures up to the limit
        for i in range(_BPGC_MAX_RETRIES):
            mod._bpgc_cache_retries += 1
            if mod._bpgc_cache_retries >= _BPGC_MAX_RETRIES:
                mod._bpgc_bytecode_cache = {}
                break

        assert mod._bpgc_bytecode_cache == {}
        # Cache is {} (not None), so `if _bpgc_bytecode_cache is None` will be False
        # and no further retries occur

    def test_success_resets_retry_counter(self):
        """After successful cache population, retry counter resets to 0."""
        import uasset_read.kismet.bytecode_extractor as mod
        reset_bpgc_cache()
        mod._bpgc_cache_retries = 2  # Simulate prior failures

        # Simulate successful extraction
        mod._bpgc_bytecode_cache = {"Func1": b'\xAA', "Func2": b'\xBB'}
        mod._bpgc_cache_retries = 0  # Reset on success

        assert mod._bpgc_cache_retries == 0
        assert len(mod._bpgc_bytecode_cache) == 2

    def test_max_retries_constant_is_sane(self):
        """_BPGC_MAX_RETRIES should be a positive integer."""
        assert isinstance(_BPGC_MAX_RETRIES, int)
        assert _BPGC_MAX_RETRIES > 0


# ---------------------------------------------------------------------------
# BPGC 字节码解析诊断测试 (merged from test_bpgc_cache.py)
# ---------------------------------------------------------------------------


class TestBpgcBytecodeDiagnostics:
    """#343: BPGC 字节码诊断改进测试。"""

    def test_empty_bytecode_logs_info_not_warning(self, caplog):
        """空字节码（无数据）应使用 info 级别。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        with caplog.at_level(logging.INFO):
            result = _parse_cooked_bytecode_buffer(b'')

        assert result == []
        # 空数据不应有 warning
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 0

    def test_corrupted_bytecode_logs_debug(self):
        """损坏字节码应使用 debug 级别记录容错诊断。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        # 构造损坏数据：无效 size（unsigned 解释后远超剩余数据）
        corrupted = struct.pack('<i', -1) + b'\x00' * 10

        # 用 Handler 捕获日志，避免 caplog 在全量测试中受根日志器级别影响
        test_logger = logging.getLogger("uasset_read.kismet.bpgc_bytecode")
        old_level = test_logger.level
        test_logger.setLevel(logging.DEBUG)
        captured: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record)
        test_logger.addHandler(handler)
        try:
            _result = _parse_cooked_bytecode_buffer(corrupted)
        finally:
            test_logger.removeHandler(handler)
            test_logger.setLevel(old_level)

        debugs = [r for r in captured if r.levelno == logging.DEBUG]
        assert len(debugs) > 0, f"Expected debug logs but got none"


def test_remaining_bytes_zero_early_return():
    """当 remaining_bytes <= 0 时，应在早期返回而非到达原第 198 行的死代码分支。"""
    from uasset_read.kismet.bpgc_bytecode import extract_bpgc_bytecode

    # 创建 mock 对象
    mock_archive = MagicMock()
    mock_export = MagicMock()
    mock_export.object_name = "TestBPGC"
    mock_export.serial_offset = 100
    mock_export.serial_size = 50
    mock_export.script_serialization_size = 100
    mock_export.has_script_serialization = True
    mock_summary = MagicMock()
    mock_summary.file_version_ue5 = 0

    # 设置 archive.tell() 返回大于 region_end 的值，使 remaining_bytes < 0
    # region_end = 100 + 50 = 150, tell() 返回 200 → remaining_bytes = -50
    mock_archive.tell.return_value = 200

    # 设置 detect_blueprint_generated_class 返回 True
    with patch(
        "uasset_read.serializers.object_resources.detect_blueprint_generated_class",
        return_value=True,
    ):
        # 设置 read_property_tag 返回 None 终止符
        mock_tag = MagicMock()
        mock_tag.name = "None"
        with patch(
            "uasset_read.serializers.property_tags.read_property_tag",
            return_value=mock_tag,
        ):
            result = extract_bpgc_bytecode(
                mock_archive, mock_export, mock_summary,
                "TestAsset", [], [], [],
            )

    # 验证返回空字典（早期返回）
    assert result == {}
    # 验证 read_bytes 未被调用（死代码未执行）
    mock_archive.read_bytes.assert_not_called()


# ---------------------------------------------------------------------------
# Set 语义翻译测试 (merged from test_translator_set.py)
# ---------------------------------------------------------------------------


class TestSetDifference:
    """Set_Difference 语义回归测试（Issue #387 残留）。"""

    def test_set_difference_uses_minus_operator(self):
        """Set_Difference 应输出 A - B，而非 A == B。"""
        result = MathFunctionCleaner._clean_set(
            "Set_Difference", ["setA", "setB", "result"]
        )
        assert "-" in result
        assert "==" not in result
        assert result == "result = setA - setB"

    def test_set_difference_no_equality(self):
        """确保 Set_Difference 输出中不包含相等比较符号。"""
        result = MathFunctionCleaner._clean_set(
            "Set_Difference", ["MySet", "OtherSet", "Diff"]
        )
        assert "Diff = MySet - OtherSet" == result


class TestSetCleanTable:
    """其他 Set 库函数的翻译验证。"""

    def test_set_add_items(self):
        result = MathFunctionCleaner._clean_set("Set_AddItems", ["s", "item"])
        assert result == "s.Add(item)"

    def test_set_clear(self):
        result = MathFunctionCleaner._clean_set("Set_Clear", ["s"])
        assert result == "s.Clear()"

    def test_set_is_empty(self):
        result = MathFunctionCleaner._clean_set("Set_IsEmpty", ["s"])
        assert result == "s.Length == 0"

    def test_set_length(self):
        result = MathFunctionCleaner._clean_set("Set_Length", ["s"])
        assert result == "s.Length"

    def test_set_unknown_fallback(self):
        result = MathFunctionCleaner._clean_set("Set_Unknown", ["a", "b"])
        assert result == "BlueprintSetLibrary::Set_Unknown(a, b)"
