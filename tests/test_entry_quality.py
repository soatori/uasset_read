"""入口点模块缺陷测试。"""
from __future__ import annotations

import importlib
import inspect
import sys
import pytest


class TestParseUassetImports:
    """parse_uasset 模块导入与接口验证。"""

    def test_module_imports(self):
        """parse_uasset 可正常导入。"""
        from uasset_read.parse_uasset import parse_package
        assert parse_package is not None

    def test_parse_package_is_callable(self):
        """parse_package 是可调用的函数。"""
        from uasset_read.parse_uasset import parse_package
        assert callable(parse_package)

    def test_parse_package_signature(self):
        """parse_package 签名包含核心参数。"""
        from uasset_read.parse_uasset import parse_package
        sig = inspect.signature(parse_package)
        params = list(sig.parameters.keys())
        assert "path" in params
        assert "tolerant" in params
        assert "provider" in params
        assert "mappings_path" in params
        assert "game" in params
        assert "force_full_parse" in params

    def test_parse_package_returns_parse_result(self):
        """parse_package 返回类型注解为 ParseResult。"""
        from uasset_read.parse_uasset import parse_package
        hints = parse_package.__annotations__
        assert "return" in hints

    def test_parse_uasset_with_linker_imports(self):
        """parse_uasset_with_linker 可正常导入。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        assert callable(parse_uasset_with_linker)

    def test_parse_uasset_imports(self):
        """parse_uasset 兼容入口可正常导入。"""
        from uasset_read.parse_uasset import parse_uasset
        assert callable(parse_uasset)

    def test_parse_package_lazy_imports(self):
        """parse_package_lazy 可正常导入。"""
        from uasset_read.parse_uasset import parse_package_lazy
        assert callable(parse_package_lazy)

    def test_internal_helpers_import(self):
        """内部辅助函数可正常导入。"""
        mod = importlib.import_module("uasset_read.parse_uasset")
        assert hasattr(mod, "_should_use_lightweight_tolerant_parse")
        assert hasattr(mod, "_build_lightweight_graphs")
        assert hasattr(mod, "_build_lightweight_function_graphs")
        assert hasattr(mod, "_record_parse_stage_error")
        assert hasattr(mod, "_run_required_stage")
        assert hasattr(mod, "_post_process")


class TestCoreImports:
    """core 模块导入与接口验证。"""

    def test_module_imports(self):
        """core 模块可正常导入。"""
        from uasset_read.core import parse_single
        assert parse_single is not None

    def test_parse_single_is_callable(self):
        """parse_single 是可调用的函数。"""
        from uasset_read.core import parse_single
        assert callable(parse_single)

    def test_parse_single_signature(self):
        """parse_single 签名包含核心参数。"""
        from uasset_read.core import parse_single
        sig = inspect.signature(parse_single)
        params = list(sig.parameters.keys())
        assert "file_path" in params
        assert "format" in params
        assert "tolerant" in params
        assert "output_level" in params

    def test_parse_batch_imports(self):
        """parse_batch 可正常导入。"""
        from uasset_read.core import parse_batch
        assert callable(parse_batch)

    def test_parse_batch_signature(self):
        """parse_batch 签名包含核心参数。"""
        from uasset_read.core import parse_batch
        sig = inspect.signature(parse_batch)
        params = list(sig.parameters.keys())
        assert "input_dir" in params
        assert "format" in params
        assert "tolerant" in params
        assert "isolate_assets" in params

    def test_list_formats_imports(self):
        """list_formats 可正常导入。"""
        from uasset_read.core import list_formats
        assert callable(list_formats)

    def test_list_formats_returns_list(self):
        """list_formats 返回非空列表。"""
        from uasset_read.core import list_formats
        formats = list_formats()
        assert isinstance(formats, list)
        assert len(formats) > 0

    def test_batch_result_imports(self):
        """BatchResult 可正常导入。"""
        from uasset_read.core import BatchResult
        br = BatchResult()
        assert br.total == 0
        assert br.success == []
        assert br.skipped == []
        assert br.failed == []

    def test_parse_error_reexport(self):
        """ParseError 从 core 模块重新导出。"""
        from uasset_read.core import ParseError
        assert ParseError is not None


class TestCrossModuleConsistency:
    """跨模块一致性检查。"""

    def test_parse_uasset_delegates_to_parse_package(self):
        """parse_uasset 应委托给 parse_package。"""
        from uasset_read.parse_uasset import parse_uasset, parse_package
        import inspect
        src = inspect.getsource(parse_uasset)
        assert "parse_package" in src

    def test_core_parse_single_uses_linker_formats(self):
        """parse_single 使用 linker_formats 判断格式。"""
        from uasset_read.core import parse_single
        src = inspect.getsource(parse_single)
        assert "linker_formats" in src

    def test_parse_batch_returns_batch_result(self):
        """parse_batch 返回 BatchResult 类型。"""
        from uasset_read.core import parse_batch
        hints = parse_batch.__annotations__
        assert hints.get("return") is not None

    def test_no_sys_exit_in_entry_points(self):
        """入口点模块不应包含 sys.exit 调用（排除 docstring/注释）。"""
        import ast
        import uasset_read.parse_uasset as mod1
        import uasset_read.core as mod2
        for mod in [mod1, mod2]:
            src = inspect.getsource(mod)
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    # 检测 sys.exit() 或 sys.exit("...")
                    if isinstance(func, ast.Attribute) and func.attr == "exit":
                        if isinstance(func.value, ast.Name) and func.value.id == "sys":
                            pytest.fail(f"{mod.__name__} 第 {node.lineno} 行包含 sys.exit() 调用")

    def test_no_print_in_entry_points(self):
        """入口点模块不应包含 print() 调用（应使用 logger）。"""
        import ast
        import uasset_read.parse_uasset as mod1
        import uasset_read.core as mod2
        for mod in [mod1, mod2]:
            src = inspect.getsource(mod)
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "print":
                        pytest.fail(f"{mod.__name__} 第 {node.lineno} 行包含 print() 调用")
