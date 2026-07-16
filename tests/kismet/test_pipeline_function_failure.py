"""decompile_single_function 失败处理回归测试。

覆盖 Issue #401-2：单函数反编译失败时返回带错误信息的结果（tolerant 模式），
而非静默丢弃返回 None。

验证场景：
- tolerant 模式下异常捕获 → 返回 bytecode_status="failed" 的结果
- tolerant 模式下 error 非空 → 返回 bytecode_status="failed" 的结果
- tolerant 模式下空表达式 → 返回 bytecode_status="failed" 的结果
- 非 tolerant 模式下异常 → 仍然 raise
- 一个函数失败、一个函数成功时，后处理正确合并结果
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from uasset_read.kismet.pipeline import decompile_single_function
from uasset_read.kismet.result import KismetDecompiledResult


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
